"""
Role:   Full-text searcher weighting every query term by its inverse document frequency.
Input:  Query string, k and SearchFilters; chunks and ranking from VectorStore.
Output: ScoredChunk list ordered by the idf-weighted ts_rank_cd sum, source "lexical_idf".
Flow:   Delegates ranking to VectorStore.lexical_search_idf(), which scores each query stem
        separately and weights it by ln((N+1)/(df+1))+1, then fetches the ranked chunks.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.models import ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.postgres import PostgresStore
from rag_lab_generator.retrieval.stores.vector_store import VectorStore


@register("searcher", "lexical_idf")
class LexicalIdfSearcher(Searcher):
    name = "lexical_idf"

    def __init__(self, store: PostgresStore, embedder: Embedder, settings: Settings) -> None:
        super().__init__(store, embedder, settings)
        self.vectors = store if isinstance(store, VectorStore) else VectorStore(store.settings)

    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]:
        pairs = self.vectors.lexical_search_idf(query, k, filters)
        chunks = self.store.fetch_chunks([chunk_id for chunk_id, _ in pairs])
        return [
            ScoredChunk(chunk=chunks[chunk_id], score=score, source=self.name)
            for chunk_id, score in pairs
            if chunk_id in chunks
        ]
