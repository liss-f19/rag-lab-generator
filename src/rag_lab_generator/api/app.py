"""
Role:   FastAPI application factory of the HTTP layer.
Input:  A Settings instance (defaults to get_settings()).
Output: A configured FastAPI app with CORS, the five routers and /api/health.
Flow:   create_app() stores Settings on app.state so routers read them from the request, enables
        CORS for the Vite dev server, includes the corpus, retrieval, graph, chat and eval
        routers and registers the health probe; app_factory() is the import string for uvicorn.
"""

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from rag_lab_generator import __version__
from rag_lab_generator.api import deps
from rag_lab_generator.api.routers import chat, corpus, graph, retrieval
from rag_lab_generator.api.routers import eval as eval_router
from rag_lab_generator.api.schemas import HealthResponse
from rag_lab_generator.config import Settings, get_settings

DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(
        title="rag-lab-generator API",
        version=__version__,
        description="RAG + LangGraph backend for the Operating Systems lab assistant",
    )
    app.state.settings = resolved
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (corpus, retrieval, graph, chat, eval_router):
        app.include_router(module.router)

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    async def health(request: Request) -> HealthResponse:
        """Summary of the running configuration plus reachability of database and corpus."""
        current: Settings = request.app.state.settings
        reachable = await run_in_threadpool(deps.db_reachable, current)
        return HealthResponse(
            version=__version__,
            llm_provider=current.llm_provider,
            llm_model=current.llm_model,
            embedding_provider=current.embedding_provider,
            rag=current.rag,
            searcher=current.searcher,
            chunker=current.chunker,
            retrieval_k=current.retrieval_k,
            data_dir=str(current.data_dir),
            db_reachable=reachable,
            corpus_present=current.raw_dir.is_dir() and any(current.raw_dir.iterdir()),
            agent_available=deps.agent_available(),
            graph_available=deps.graph_available(),
            strategies=deps.available_strategies(),
        )

    return app


def app_factory() -> FastAPI:
    """Entry point used by `uvicorn --factory`, so --reload can re-import the application."""
    return create_app(get_settings())
