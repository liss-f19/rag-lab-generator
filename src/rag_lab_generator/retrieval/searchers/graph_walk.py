"""
Role:   Graph searcher: seeds the knowledge graph from a vector/lexical hit list and from query
        terms, then spreads activation over the edges to reach chunks a flat search would miss.
Input:  GraphStore (nodes, edges, node<->chunk links), an inner Searcher, Settings.graph_hops;
        query, k and SearchFilters at search time.
Output: Ranked ScoredChunk list with source "graph_walk"; each chunk carries the node path that
        explains it in metadata["path"], and the run trace is kept in self.last_trace.
Flow:   1. seed nodes from the inner searcher's top-k chunks (rank-weighted) and from query
        tokens/bigrams matching API_FUNCTION or CONCEPT labels, every seed divided by
        log2(2 + chunks it owns) so a hub term contributes less than a specific one;
        2. one best-first walk per seed up to settings.graph_hops, edges followed in both
        directions and multiplied by a per-edge-kind decay, never spreading further through a
        course node and damping arrivals at code files; 3. score a node and then a chunk by its
        strongest path times a bounded bonus per further corroboration, so several seeds still
        beat one but a keyword-dense listing cannot win on owner count alone, keeping only chunk
        ids of the requested strategy; 4. fetch the chunk models, apply the
        remaining filters and rank by score, then by the inner searcher's rank, then by chunk
        index, letting code chunks take at most code_chunk_share of the returned k.
"""

import heapq
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, cast

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, ChunkKind, EdgeKind, NodeKind, ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.graph_store import GraphStore
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

# Activation is multiplied by this factor for every edge traversed, per edge kind.
EDGE_DECAY: dict[str, float] = {
    EdgeKind.CONTAINS.value: 0.9,
    EdgeKind.USES_API.value: 0.8,
    EdgeKind.COVERS_CONCEPT.value: 0.8,
    EdgeKind.SOLVED_BY.value: 0.7,
    EdgeKind.RELATED_TO.value: 0.7,
    EdgeKind.COVERED_BY_LECTURE.value: 0.6,
    EdgeKind.PREREQUISITE_OF.value: 0.4,
}
DEFAULT_DECAY = 0.5
MIN_ACTIVATION = 1e-4
TERM_SEED_PENALTY = 0.5
CANDIDATE_LIMIT = 300
# Chunks a node owns; a term node covering half the corpus must not seed as strongly as a rare one.
UNRANKED = 1 << 30
SEED_LABEL_KINDS = (NodeKind.API_FUNCTION.value, NodeKind.CONCEPT.value)
# Documents are seeded by their own name too, so "netcat" or "deadlocks" reaches the lab/lecture.
DOCUMENT_SEED_KINDS = (NodeKind.LAB.value, NodeKind.LECTURE.value)
# Taxonomy roots connect everything they own; activation reaches them but never passes through.
HUB_KINDS = (NodeKind.COURSE.value,)

_WORD_RE = re.compile(r"[a-z_][a-z0-9_]*")


@dataclass
class _Activation:
    """Best activation reached for one node from one seed, with the path that produced it."""

    score: float
    hops: int
    path: list[str] = field(default_factory=list)


@register("searcher", "graph_walk")
class GraphWalkSearcher(Searcher):
    name = "graph_walk"
    inner_searcher_name: str = "hybrid_rrf"
    fallback_searcher_name: str = "lexical"
    # Source files are dense in api calls, so activation drains into them; hold them back.
    code_node_factor: float = 0.4
    code_chunk_share: float = 0.25
    # Corroboration is worth a bounded bonus over the best path, never a plain sum: a long
    # source listing is owned by dozens of api nodes without being dozens of times more relevant.
    corroboration_bonus: float = 0.15
    # Let a lab or lecture be seeded by its own name, not only through its terminology.
    document_name_seeds: bool = True

    def __init__(
        self,
        store: PostgresStore,
        embedder: Embedder,
        settings: Settings,
        inner: Searcher | None = None,
        inner_name: str | None = None,
    ) -> None:
        super().__init__(store, embedder, settings)
        # reuse the injected store when it already speaks the graph api, otherwise open one
        self.graph_store: GraphStore = (
            cast(GraphStore, store) if hasattr(store, "load_graph") else GraphStore(settings)
        )
        self.inner_name = inner_name or (
            inner.name if inner is not None else self.inner_searcher_name
        )
        self.last_trace: dict[str, Any] = {}
        self._inner = inner
        self._inner_missing = False
        self._labels: dict[str, list[str]] | None = None

    # ------------------------------------------------------------ inner searcher

    @property
    def inner(self) -> Searcher | None:
        """Create the seeding searcher on first use; fall back when the preferred one is absent."""
        if self._inner is not None or self._inner_missing:
            return self._inner
        available = registry.available("searcher")
        for candidate in (self.inner_name, self.fallback_searcher_name):
            if candidate in available and candidate != self.name:
                self._inner = cast(
                    Searcher,
                    registry.create(
                        "searcher",
                        candidate,
                        store=self.store,
                        embedder=self.embedder,
                        settings=self.settings,
                    ),
                )
                self.inner_name = candidate
                return self._inner
        self._inner_missing = True
        return None

    # ------------------------------------------------------------ search

    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]:
        graph = self.graph_store.load_graph()
        direct, ranks = self._inner_hits(query, k, filters)
        seeds = self._seed_nodes(query, graph, direct, ranks)
        contributions = self._spread(graph, seeds)
        candidates = self._collect_chunks(graph, contributions, direct, filters)
        results = self._materialize(candidates, ranks, k, filters)
        self.last_trace = {
            "seed_nodes": sorted(seeds),
            "seed_weights": {node: round(score, 4) for node, score in sorted(seeds.items())},
            "activated_nodes": len(contributions),
            "inner_searcher": self.inner_name if self.inner is not None else None,
            "paths": {sc.chunk.id: sc.chunk.metadata.get("path", []) for sc in results},
        }
        return results

    def _inner_hits(
        self, query: str, k: int, filters: SearchFilters
    ) -> tuple[dict[str, float], dict[str, int]]:
        """Run the seeding searcher; its ranking is kept so the graph adds to it, not over it."""
        inner = self.inner
        if inner is None:
            return {}, {}
        hits = inner.search(query, k, filters)
        direct = {hit.chunk.id: 1.0 / (1.0 + rank) for rank, hit in enumerate(hits)}
        ranks = {hit.chunk.id: rank for rank, hit in enumerate(hits)}
        return direct, ranks

    def _seed_nodes(
        self, query: str, graph: Any, direct: dict[str, float], ranks: dict[str, int]
    ) -> dict[str, float]:
        """Entry nodes from the searcher's hits and from query term labels, damped by hub size."""
        seeds: dict[str, float] = {}

        def offer(node_id: str, score: float) -> None:
            damped = score / _hub_damping(graph, node_id)
            if damped > seeds.get(node_id, 0.0):
                seeds[node_id] = damped

        if direct:
            mapping = self.graph_store.nodes_for_chunks(sorted(direct))
            for chunk_id in sorted(direct, key=lambda c: ranks.get(c, UNRANKED)):
                for node_id in mapping.get(chunk_id, []):
                    if graph.has_node(node_id):
                        offer(node_id, direct[chunk_id])
        for node_id in self._label_matches(query, graph):
            offer(node_id, TERM_SEED_PENALTY)
        return seeds

    def _label_matches(self, query: str, graph: Any) -> list[str]:
        """Match query tokens and bigrams against api function and concept labels."""
        index = self._label_index(graph)
        tokens = _WORD_RE.findall(query.lower())
        terms = set(tokens)
        terms.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False))
        matched: list[str] = []
        for term in sorted(terms):
            matched.extend(index.get(term, []))
        return matched

    def _label_index(self, graph: Any) -> dict[str, list[str]]:
        if self._labels is not None:
            return self._labels
        index: dict[str, list[str]] = {}
        for node_id, data in graph.nodes(data=True):
            kind = data.get("kind")
            if kind in SEED_LABEL_KINDS:
                index.setdefault(str(data.get("label", "")).lower(), []).append(node_id)
            elif kind in DOCUMENT_SEED_KINDS and self.document_name_seeds:
                # a document answers to its own name as well as to its title
                for alias in _document_aliases(node_id, data):
                    index.setdefault(alias, []).append(node_id)
        self._labels = index
        return index

    def _spread(self, graph: Any, seeds: dict[str, float]) -> dict[str, tuple[float, list[str]]]:
        """Walk from every seed separately, then sum each node's per-seed contributions."""
        parts: dict[str, list[float]] = defaultdict(list)
        best: dict[str, _Activation] = {}
        for seed_id, seed_score in sorted(seeds.items()):
            for node_id, activation in self._walk_from(graph, seed_id, seed_score).items():
                parts[node_id].append(activation.score)
                known = best.get(node_id)
                if known is None or activation.score > known.score:
                    best[node_id] = activation
        return {node: (self._combine(scores), best[node].path) for node, scores in parts.items()}

    def _walk_from(self, graph: Any, seed_id: str, seed_score: float) -> dict[str, _Activation]:
        """Best-first decayed spreading from one seed: child = parent * decay(edge kind)."""
        best: dict[str, _Activation] = {
            seed_id: _Activation(score=seed_score, hops=0, path=[seed_id])
        }
        heap: list[tuple[float, int, str]] = [(-seed_score, 0, seed_id)]
        max_hops = max(0, self.settings.graph_hops)
        while heap:
            negative, hops, node_id = heapq.heappop(heap)
            current = best[node_id]
            if -negative < current.score or hops > current.hops:
                continue
            if hops >= max_hops or graph.nodes[node_id].get("kind") in HUB_KINDS:
                continue
            for neighbour, kind in _neighbours(graph, node_id):
                score = current.score * EDGE_DECAY.get(kind, DEFAULT_DECAY)
                if graph.nodes[neighbour].get("kind") == NodeKind.CODE_FILE.value:
                    score *= self.code_node_factor
                if score < MIN_ACTIVATION:
                    continue
                known = best.get(neighbour)
                if known is not None and known.score >= score:
                    continue
                best[neighbour] = _Activation(
                    score=score, hops=hops + 1, path=[*current.path, neighbour]
                )
                heapq.heappush(heap, (-score, hops + 1, neighbour))
        return best

    def _collect_chunks(
        self,
        graph: Any,
        contributions: dict[str, tuple[float, list[str]]],
        direct: dict[str, float],
        filters: SearchFilters,
    ) -> dict[str, tuple[float, str, list[str]]]:
        """Accumulate every activated node's contribution onto the chunks it owns."""
        prefix = f"{filters.strategy}:"
        parts: dict[str, list[float]] = defaultdict(list)
        best: dict[str, tuple[float, str, list[str]]] = {}
        for node_id, (activation, path) in contributions.items():
            # drop whole nodes the filters exclude so the candidate cap is spent on usable chunks
            if not _node_passes(graph.nodes[node_id], filters):
                continue
            for chunk_id in graph.nodes[node_id].get("chunk_ids", []):
                if not chunk_id.startswith(prefix):
                    continue
                parts[chunk_id].append(activation)
                known = best.get(chunk_id)
                if known is None or activation > known[0]:
                    best[chunk_id] = (activation, node_id, list(path))
        # the searcher's own evidence applies to the chunk it returned, not to its node siblings
        for chunk_id, score in direct.items():
            if chunk_id.startswith(prefix):
                parts[chunk_id].append(score)
                best.setdefault(chunk_id, (score, "", []))
        return {
            chunk_id: (self._combine(scores), best[chunk_id][1], best[chunk_id][2])
            for chunk_id, scores in parts.items()
        }

    def _combine(self, scores: list[float]) -> float:
        """Strongest evidence, raised by a bounded bonus for every further corroboration."""
        if not scores:
            return 0.0
        return max(scores) * (1.0 + self.corroboration_bonus * math.log1p(len(scores) - 1))

    def _materialize(
        self,
        candidates: dict[str, tuple[float, str, list[str]]],
        ranks: dict[str, int],
        k: int,
        filters: SearchFilters,
    ) -> list[ScoredChunk]:
        """Fetch the best candidates, apply the remaining filters and rank them."""
        ordered = sorted(
            candidates,
            key=lambda c: (-candidates[c][0], ranks.get(c, UNRANKED), c),
        )
        chunk_ids = ordered[:CANDIDATE_LIMIT]
        fetched = self.graph_store.fetch_chunks(chunk_ids)
        rows = [
            (candidates[c][0], ranks.get(c, UNRANKED), fetched[c].idx, c)
            for c in chunk_ids
            if c in fetched and _passes(fetched[c], filters)
        ]
        rows.sort(key=lambda row: (-row[0], row[1], row[2], row[3]))
        # source listings answer few questions on their own, so they may not crowd out the prose
        code_budget = max(1, int(k * self.code_chunk_share)) if k > 0 else 0
        code_taken = 0
        results: list[ScoredChunk] = []
        for score, _, _, chunk_id in rows:
            if len(results) >= k:
                break
            chunk = fetched[chunk_id]
            is_code = chunk.kind is ChunkKind.CODE
            if is_code and code_taken >= code_budget:
                continue
            code_taken += int(is_code)
            _, node_id, path = candidates[chunk_id]
            enriched = chunk.model_copy(deep=True)
            enriched.metadata = {**chunk.metadata, "path": path, "node_id": node_id}
            results.append(ScoredChunk(chunk=enriched, score=score, source=self.name))
        return results


def _document_aliases(node_id: str, data: dict[str, Any]) -> set[str]:
    """Names a lab or lecture answers to: its title, its id suffix and its slug."""
    aliases = {str(data.get("label", "")).lower(), node_id.rsplit("/", 1)[-1].lower()}
    slug = data.get("properties", {}).get("slug")
    if isinstance(slug, str) and slug:
        aliases.add(slug.lower())
    return {alias for alias in aliases if alias}


def _hub_damping(graph: Any, node_id: str) -> float:
    """Divisor growing with the number of chunks a node owns: log2(2 + n)."""
    owned = len(graph.nodes[node_id].get("chunk_ids", [])) if graph.has_node(node_id) else 0
    return math.log2(2.0 + owned)


def _neighbours(graph: Any, node_id: str) -> list[tuple[str, str]]:
    """Both directions of every incident edge, with the edge kind, in a deterministic order."""
    pairs: set[tuple[str, str]] = set()
    for _, dst, data in graph.out_edges(node_id, data=True):
        pairs.add((dst, str(data.get("kind", ""))))
    for src, _, data in graph.in_edges(node_id, data=True):
        pairs.add((src, str(data.get("kind", ""))))
    return sorted(pairs)


def _passes(chunk: Chunk, filters: SearchFilters) -> bool:
    if filters.course and chunk.course.value != filters.course:
        return False
    if filters.lab_id and chunk.lab_id != filters.lab_id:
        return False
    if filters.kinds and chunk.kind.value not in filters.kinds:
        return False
    return True


def _node_passes(data: dict[str, Any], filters: SearchFilters) -> bool:
    """Course and lab filters applied to node attributes; terminology nodes carry neither."""
    course = data.get("course")
    if filters.course and course and course != filters.course:
        return False
    lab_id = data.get("lab_id")
    return not (filters.lab_id and lab_id and lab_id != filters.lab_id)
