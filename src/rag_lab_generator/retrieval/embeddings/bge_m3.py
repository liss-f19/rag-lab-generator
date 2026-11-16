"""
Role:   Production embedder backed by a sentence-transformers model (BAAI/bge-m3 by default).
Input:  Settings (embedding_model, embedding_batch_size, embedding_dim); texts at call time.
Output: L2-normalized vectors of the model dimension.
Flow:   Loads the SentenceTransformer lazily on the first embed call, encodes in batches with
        normalize_embeddings=True and returns plain float lists; dim is read from the model.
"""

from typing import Any

from rag_lab_generator.config import Settings
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder


@register("embedder", "bge_m3")
class BgeM3Embedder(Embedder):
    name = "bge_m3"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._model: Any | None = None
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = int(self._load().get_sentence_embedding_dimension())
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(
            texts,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [[float(x) for x in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _load(self) -> Any:
        """Import and instantiate the model on first use so tests never touch the network."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model
