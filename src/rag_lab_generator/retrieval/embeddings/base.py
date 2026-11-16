"""
Role:   Abstract base for text embedders.
Input:  Settings (embedding_model, embedding_dim, batch size); texts at call time.
Output: Float vectors of length dim.
Flow:   Subclasses implement embed_documents() and embed_query(); base defines the contract and
        the vector space name under which stored vectors are looked up (defaults to the name,
        overridden by embedders that reproduce another embedder's vectors).
"""

from abc import ABC, abstractmethod

from rag_lab_generator.config import Settings


class Embedder(ABC):
    name: str = "base"
    space: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def vector_space(self) -> str:
        """Embedder column value of the stored vectors this embedder is compatible with."""
        return self.space or self.name

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...
