"""
Role:   Abstract base for chunk searchers (lexical, dense, hybrid, graph walk).
Input:  PostgresStore, Embedder (may be unused), Settings; query string and k at search time.
Output: Ranked list of ScoredChunk, best first, length <= k.
Flow:   Subclasses implement search(); filters restrict by strategy (chunker name), course, lab.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from rag_lab_generator.config import Settings
from rag_lab_generator.models import ScoredChunk
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.stores.postgres import PostgresStore


class SearchFilters(BaseModel):
    strategy: str
    course: str | None = None
    lab_id: str | None = None
    kinds: list[str] | None = None


class Searcher(ABC):
    name: str = "base"

    def __init__(self, store: PostgresStore, embedder: Embedder, settings: Settings) -> None:
        self.store = store
        self.embedder = embedder
        self.settings = settings

    @abstractmethod
    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]: ...
