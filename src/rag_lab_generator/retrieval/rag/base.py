"""
Role:   Abstract base for RAG retrieval strategies (vector, graph).
Input:  Searcher, PostgresStore, Settings; query and k at retrieve time.
Output: RetrievedContext with ranked chunks and a trace explaining how they were found.
Flow:   Subclasses implement retrieve(); the agent and eval runner only depend on this contract.
"""

from abc import ABC, abstractmethod

from rag_lab_generator.config import Settings
from rag_lab_generator.models import RetrievedContext
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.postgres import PostgresStore


class RAG(ABC):
    name: str = "base"

    def __init__(self, searcher: Searcher, store: PostgresStore, settings: Settings) -> None:
        self.searcher = searcher
        self.store = store
        self.settings = settings

    @abstractmethod
    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext: ...
