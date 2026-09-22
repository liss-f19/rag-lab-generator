"""
Role:   Default searcher: reciprocal rank fusion of a lexical and the dense ranking.
Input:  Query string, k and SearchFilters; VectorStore for the dense side; the embedder.
Output: ScoredChunk list with source "hybrid_rrf" and per-source ranks in chunk.metadata["ranks"].
Flow:   Builds its lexical side through the registry (name from lexical_name, so the idf variant
        is the same class with another component), pulls the top 3k of both sides, fuses them with
        score = sum 1 / (rrf_k + rank), keeps the best k and copies the ranks into the metadata.
        rrf_fuse() is a pure function so the math is unit tested.
"""

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.models import ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.postgres import PostgresStore
from rag_lab_generator.retrieval.stores.vector_store import VectorStore

CANDIDATE_FACTOR = 3


def rrf_fuse(
    rank_lists: dict[str, list[str]], rrf_k: int
) -> list[tuple[str, float, dict[str, int]]]:
    """Fuse ranked id lists: score = sum over sources of 1 / (rrf_k + rank), rank starting at 1."""
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for source, ids in rank_lists.items():
        for position, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + position)
            ranks.setdefault(chunk_id, {})[source] = position
    fused = [(chunk_id, score, ranks[chunk_id]) for chunk_id, score in scores.items()]
    fused.sort(key=lambda item: (-item[1], item[0]))
    return fused


@register("searcher", "hybrid_rrf")
class HybridRRFSearcher(Searcher):
    name = "hybrid_rrf"
    lexical_name = "lexical"

    def __init__(
        self,
        store: PostgresStore,
        embedder: Embedder,
        settings: Settings,
        lexical_name: str | None = None,
    ) -> None:
        super().__init__(store, embedder, settings)
        self.vectors = store if isinstance(store, VectorStore) else VectorStore(store.settings)
        self.lexical_name = lexical_name or type(self).lexical_name
        self._lexical: Searcher | None = None

    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]:
        candidates = CANDIDATE_FACTOR * k
        lexical = self.lexical_searcher().search(query, candidates, filters)
        dense = self.vectors.dense_search(
            self.embedder.embed_query(query), self.embedder.vector_space, candidates, filters
        )
        fused = rrf_fuse(
            {
                self.lexical_name: [hit.chunk.id for hit in lexical],
                "dense": [chunk_id for chunk_id, _ in dense],
            },
            self.settings.rrf_k,
        )[:k]
        chunks = self.store.fetch_chunks([chunk_id for chunk_id, _, _ in fused])
        results: list[ScoredChunk] = []
        for chunk_id, score, ranks in fused:
            chunk = chunks.get(chunk_id)
            if chunk is None:
                continue
            # keep the per-source ranks next to the chunk without mutating the stored model
            traced = chunk.model_copy(update={"metadata": {**chunk.metadata, "ranks": ranks}})
            results.append(ScoredChunk(chunk=traced, score=score, source=self.name))
        return results

    def lexical_searcher(self) -> Searcher:
        """Build the lexical side through the registry on first use."""
        if self._lexical is None:
            created: Searcher = registry.create(
                "searcher",
                self.lexical_name,
                store=self.store,
                embedder=self.embedder,
                settings=self.settings,
            )
            self._lexical = created
        return self._lexical


@register("searcher", "hybrid_rrf_idf")
class HybridRRFIdfSearcher(HybridRRFSearcher):
    name = "hybrid_rrf_idf"
    lexical_name = "lexical_idf"
