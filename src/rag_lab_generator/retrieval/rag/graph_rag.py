"""
Role:   GraphRAG strategy: retrieval driven by the knowledge graph instead of by vectors alone.
Input:  A Searcher (wrapped as the graph walker's seed source), GraphStore, Settings; query,
        k and SearchFilters at retrieve time.
Output: RetrievedContext with graph-scored chunks and a trace of seeds, activated nodes and paths.
Flow:   Ensure the searcher is a GraphWalkSearcher (wrapping the injected one as its inner
        searcher), run the walk, then for every returned task chunk pull up to two sibling
        section chunks of the same lab that share an API_FUNCTION so the prompt holds both the
        tutorial explanation and the task example; finally assemble the trace with latencies.
"""

from time import perf_counter
from typing import Any, cast

from rag_lab_generator.config import Settings
from rag_lab_generator.models import EdgeKind, NodeKind, RetrievedContext, ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.searchers.graph_walk import GraphWalkSearcher
from rag_lab_generator.retrieval.stores.graph_store import GraphStore
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

SIBLINGS_PER_TASK = 2
SIBLING_SCORE_FACTOR = 0.5
SIBLING_SOURCE = "graph_rag_sibling"


@register("rag", "graph")
class GraphRAG(RAG):
    name = "graph"

    def __init__(self, searcher: Searcher, store: PostgresStore, settings: Settings) -> None:
        super().__init__(searcher, store, settings)
        self.graph_store: GraphStore = (
            cast(GraphStore, store) if hasattr(store, "load_graph") else GraphStore(settings)
        )
        # a plain searcher becomes the seed source of a graph walker
        if isinstance(searcher, GraphWalkSearcher):
            self.walker = searcher
        else:
            self.walker = GraphWalkSearcher(
                self.graph_store, searcher.embedder, settings, inner=searcher
            )
        self.searcher = self.walker

    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext:
        started = perf_counter()
        results = self.walker.search(query, k, filters)
        graph = self.graph_store.load_graph()
        siblings = self._task_siblings(graph, results, filters)
        chunks = [*results, *siblings]
        trace: dict[str, Any] = {
            "seed_nodes": self.walker.last_trace.get("seed_nodes", []),
            "seed_weights": self.walker.last_trace.get("seed_weights", {}),
            "activated_nodes": self.walker.last_trace.get("activated_nodes", 0),
            "inner_searcher": self.walker.last_trace.get("inner_searcher"),
            "paths": {sc.chunk.id: sc.chunk.metadata.get("path", []) for sc in chunks},
            "siblings": len(siblings),
            "latency_ms": round((perf_counter() - started) * 1000, 3),
        }
        return RetrievedContext(query=query, rag=self.name, chunks=chunks, trace=trace)

    def _task_siblings(
        self, graph: Any, results: list[ScoredChunk], filters: SearchFilters
    ) -> list[ScoredChunk]:
        """For every task chunk, add section chunks of the same lab sharing an api function."""
        taken = {sc.chunk.id for sc in results}
        wanted: dict[str, tuple[float, list[str]]] = {}
        prefix = f"{filters.strategy}:"
        for scored in results:
            node_id = scored.chunk.metadata.get("node_id")
            if not isinstance(node_id, str) or not graph.has_node(node_id):
                continue
            if graph.nodes[node_id].get("kind") != NodeKind.TASK.value:
                continue
            lab_id = graph.nodes[node_id].get("lab_id")
            found = 0
            for api_id in _api_neighbours(graph, node_id):
                for section_id in _section_neighbours(graph, api_id, lab_id):
                    for chunk_id in graph.nodes[section_id].get("chunk_ids", []):
                        if chunk_id in taken or not chunk_id.startswith(prefix):
                            continue
                        taken.add(chunk_id)
                        wanted[chunk_id] = (
                            scored.score * SIBLING_SCORE_FACTOR,
                            [node_id, api_id, section_id],
                        )
                        found += 1
                        break
                    if found >= SIBLINGS_PER_TASK:
                        break
                if found >= SIBLINGS_PER_TASK:
                    break
        fetched = self.graph_store.fetch_chunks(sorted(wanted))
        siblings: list[ScoredChunk] = []
        for chunk_id, (score, path) in sorted(wanted.items(), key=lambda i: (-i[1][0], i[0])):
            chunk = fetched.get(chunk_id)
            if chunk is None:
                continue
            enriched = chunk.model_copy(deep=True)
            enriched.metadata = {**chunk.metadata, "path": path, "node_id": path[-1]}
            siblings.append(ScoredChunk(chunk=enriched, score=score, source=SIBLING_SOURCE))
        return siblings


def _api_neighbours(graph: Any, node_id: str) -> list[str]:
    return sorted(
        {
            dst
            for _, dst, data in graph.out_edges(node_id, data=True)
            if data.get("kind") == EdgeKind.USES_API.value
        }
    )


def _section_neighbours(graph: Any, api_id: str, lab_id: str | None) -> list[str]:
    return sorted(
        {
            src
            for src, _, _ in graph.in_edges(api_id, data=True)
            if graph.nodes[src].get("kind") == NodeKind.SECTION.value
            and (lab_id is None or graph.nodes[src].get("lab_id") == lab_id)
        }
    )
