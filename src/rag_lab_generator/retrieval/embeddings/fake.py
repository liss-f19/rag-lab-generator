"""
Role:   Offline deterministic embedder used by unit tests and by runs without a model download.
Input:  Settings (embedding_dim); texts at call time.
Output: Unit-length vectors of embedding_dim floats, identical for identical texts.
Flow:   Hashes the text with sha256, seeds a numpy RandomState from the digest, draws a normal
        vector and normalizes it, so cosine similarity of equal texts is exactly 1.0.
"""

import hashlib

import numpy as np

from rag_lab_generator.config import Settings
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder

_SEED_MODULUS = 2**32


@register("embedder", "fake")
class FakeEmbedder(Embedder):
    name = "fake"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._dim = settings.embedding_dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        """Derive a stable unit vector from the sha256 digest of the text."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big") % _SEED_MODULUS
        raw = np.random.RandomState(seed).normal(size=self._dim)
        norm = float(np.linalg.norm(raw))
        vector = raw / norm if norm else np.ones(self._dim) / np.sqrt(self._dim)
        return [float(x) for x in vector]
