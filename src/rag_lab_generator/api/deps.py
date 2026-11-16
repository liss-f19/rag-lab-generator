"""
Role:   Lazy wiring between the HTTP layer and the retrieval / agent layers.
Input:  Settings plus the strategy names chosen by one request.
Output: Store, embedder, searcher and RAG instances; HTTPException(503) when a piece is missing.
Flow:   Every factory imports its module inside the function so the API boots while other layers
        are unfinished; translate() turns ImportError, unknown strategy names and database
        failures into HTTP errors with a readable detail; embedders are cached per process so
        the model weights load only once; ensure_chunker() rejects a chunker name the registry
        does not know, and the probes answer the health endpoint.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.registry import UnknownStrategyError

if TYPE_CHECKING:
    from rag_lab_generator.retrieval.embeddings.base import Embedder
    from rag_lab_generator.retrieval.rag.base import RAG
    from rag_lab_generator.retrieval.searchers.base import Searcher
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore
    from rag_lab_generator.retrieval.stores.postgres import PostgresStore

UNAVAILABLE = 503

# Embedders are cached for the process: the model weights load on the first query only.
_EMBEDDERS: dict[tuple[str, str], Embedder] = {}


def unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=UNAVAILABLE, detail=detail)


@contextmanager
def translate(what: str) -> Iterator[None]:
    """Turn layer failures into HTTP errors so an unfinished module never crashes a request."""
    try:
        yield
    except HTTPException:
        raise
    except UnknownStrategyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ImportError, AttributeError) as exc:
        raise unavailable(f"{what} is not available yet: {exc}") from exc
    except Exception as exc:
        raise unavailable(f"{what} failed: {type(exc).__name__}: {exc}") from exc


def open_store(settings: Settings) -> PostgresStore:
    """Prefer the vector store; fall back to the plain chunk store while it is being written."""
    try:
        from rag_lab_generator.retrieval.stores.vector_store import VectorStore

        return VectorStore(settings)
    except ImportError:
        with translate("the chunk store"):
            from rag_lab_generator.retrieval.stores.postgres import PostgresStore

            return PostgresStore(settings)


def open_graph_store(settings: Settings) -> GraphStore:
    with translate("the knowledge graph store"):
        from rag_lab_generator.retrieval.stores.graph_store import GraphStore

        return GraphStore(settings)


def build_embedder(settings: Settings, name: str) -> Embedder:
    """Reuse one embedder per (name, model): loading a sentence-transformer costs seconds."""
    key = (name, settings.embedding_model)
    cached = _EMBEDDERS.get(key)
    if cached is not None:
        return cached
    with translate(f"embedder {name!r}"):
        embedder: Embedder = registry.create("embedder", name, settings=settings)
    _EMBEDDERS[key] = embedder
    return embedder


def build_searcher(
    settings: Settings, name: str, store: PostgresStore, embedder: Embedder
) -> Searcher:
    with translate(f"searcher {name!r}"):
        searcher: Searcher = registry.create(
            "searcher", name, store=store, embedder=embedder, settings=settings
        )
        return searcher


def build_rag(settings: Settings, rag: str, searcher: Searcher, store: PostgresStore) -> RAG:
    with translate(f"rag strategy {rag!r}"):
        built: RAG = registry.create("rag", rag, searcher=searcher, store=store, settings=settings)
        return built


def ensure_chunker(name: str) -> None:
    """A chunker name only filters rows, so nothing else would notice it is not registered."""
    with translate("the chunker registry"):
        known = registry.available("chunker")
    if name not in known:
        raise HTTPException(
            status_code=400,
            detail=f"unknown chunker strategy {name!r}; available: {known}",
        )


def build_pipeline(settings: Settings, rag: str, searcher: str, embedder: str) -> RAG:
    """Assemble store -> embedder -> searcher -> rag with one 503 for whatever is missing."""
    store = open_store(settings)
    model = build_embedder(settings, embedder)
    return build_rag(settings, rag, build_searcher(settings, searcher, store, model), store)


# ---------------------------------------------------------------- probes


def db_reachable(settings: Settings) -> bool:
    try:
        store = open_store(settings)
        with store.connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def available_strategies() -> dict[str, list[str]]:
    """Registry contents per kind; an unfinished strategy package yields an empty list."""
    result: dict[str, list[str]] = {}
    for kind in registry.KINDS:
        try:
            result[kind] = registry.available(kind)
        except Exception:
            result[kind] = []
    return result


def module_attr(module_name: str, attribute: str) -> Any | None:
    """Import a module of another layer and return one attribute, or None when absent."""
    try:
        return getattr(import_module(module_name), attribute, None)
    except Exception:
        return None


def agent_available() -> bool:
    return module_attr("rag_lab_generator.agent.graph", "build_agent") is not None


def graph_available() -> bool:
    return module_attr("rag_lab_generator.retrieval.stores.graph_store", "GraphStore") is not None
