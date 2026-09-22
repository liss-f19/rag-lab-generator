"""
Role:   Dense searcher: cosine nearest neighbours over the embeddings of one embedder.
Input:  Query string, k and SearchFilters; the embedder given by the factory.
Output: ScoredChunk list ordered by cosine similarity, source "dense".
Flow:   Embeds the query, asks VectorStore.dense_search() for the top k (chunk_id, score) pairs
        scoped to the embedder name and the filters, then fetches the chunks.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.models import ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.postgres import PostgresStore
from rag_lab_generator.retrieval.stores.vector_store import VectorStore


@register("searcher", "dense")
class DenseSearcher(Searcher):
    name = "dense"

    def __init__(self, store: PostgresStore, embedder: Embedder, settings: Settings) -> None:
        super().__init__(store, embedder, settings)
        self.vectors = store if isinstance(store, VectorStore) else VectorStore(store.settings)

    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]:
        query_vec = self.embedder.embed_query(query)
        pairs = self.vectors.dense_search(query_vec, self.embedder.vector_space, k, filters)
        chunks = self.store.fetch_chunks([chunk_id for chunk_id, _ in pairs])
        return [
            ScoredChunk(chunk=chunks[chunk_id], score=score, source=self.name)
            for chunk_id, score in pairs
            if chunk_id in chunks
        ]
