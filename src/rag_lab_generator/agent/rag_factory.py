"""
Role:   Lazy construction of the retrieval stack the agent tools query.
Input:  Settings (store url, embedder, searcher, rag names) and an optional rag override.
Output: A callable returning a ready RAG, or RagUnavailableError with an actionable message.
Flow:   build_rag() picks the vector store (VectorStore when the retrieval layer provides it,
        PostgresStore otherwise), then creates embedder, searcher and rag through the registry;
        make_rag_factory() wraps it in a caching callable so the stack is built at most once,
        and every import or registry failure becomes a RagUnavailableError.
"""

import importlib
from collections.abc import Callable

from rag_lab_generator.config import Settings
from rag_lab_generator.registry import UnknownStrategyError, create
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

RagFactory = Callable[[], RAG]

SETUP_HINT = "run `rag-lab ingest`, `rag-lab chunk` and `rag-lab index` first"


class RagUnavailableError(RuntimeError):
    """Raised when the retrieval stack cannot be built or cannot answer."""


def build_store(settings: Settings) -> PostgresStore:
    """Return the vector-aware store when the retrieval layer ships one, else the base store."""
    try:
        module = importlib.import_module("rag_lab_generator.retrieval.stores.vector_store")
    except ImportError:
        return PostgresStore(settings)
    vector_store = getattr(module, "VectorStore", None)
    if vector_store is None:
        return PostgresStore(settings)
    store: PostgresStore = vector_store(settings)
    return store


def build_rag(settings: Settings, rag_name: str | None = None) -> RAG:
    """Create embedder, searcher and rag through the registry; never import them directly."""
    name = rag_name or settings.rag
    try:
        store = build_store(settings)
        embedder = create("embedder", settings.embedding_provider, settings=settings)
        searcher = create(
            "searcher", settings.searcher, store=store, embedder=embedder, settings=settings
        )
        rag: RAG = create("rag", name, searcher=searcher, store=store, settings=settings)
    except UnknownStrategyError as exc:
        raise RagUnavailableError(
            f"retrieval strategy missing: {exc}. The retrieval layer may not be implemented yet."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - any construction failure must stay actionable
        raise RagUnavailableError(
            f"cannot build the retrieval stack ({exc}); {SETUP_HINT}"
        ) from exc
    return rag


class CachedRagFactory:
    """Builds the RAG on first use and reuses it for every later tool call."""

    def __init__(self, settings: Settings, rag_name: str | None = None) -> None:
        self.settings = settings
        self.rag_name = rag_name
        self._rag: RAG | None = None

    def __call__(self) -> RAG:
        if self._rag is None:
            self._rag = build_rag(self.settings, self.rag_name)
        return self._rag


def make_rag_factory(settings: Settings, rag_name: str | None = None) -> RagFactory:
    return CachedRagFactory(settings, rag_name)
