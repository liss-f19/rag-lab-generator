"""
Role:   Retrieval endpoints: one query, a side-by-side comparison and the strategy catalogue.
Input:  RetrieveRequest / CompareRequest bodies; Settings from app.state.
Output: RetrieveResponse, CompareResponse, StrategiesResponse.
Flow:   Request values fall back to the Settings defaults, the chunker name is validated against
        the registry (an unknown one is a 400, never an empty result), api.deps assembles store
        -> embedder -> searcher -> rag lazily, the blocking retrieve() runs in a threadpool, and
        the compare route repeats that sequentially keeping per-column latency and errors.
"""

from time import perf_counter

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from rag_lab_generator.api import deps
from rag_lab_generator.api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareResult,
    ResolvedConfig,
    RetrieveRequest,
    RetrieveResponse,
    StrategiesResponse,
)
from rag_lab_generator.config import Settings
from rag_lab_generator.models import RetrievedContext

router = APIRouter(prefix="/api", tags=["retrieval"])


def settings_of(request: Request) -> Settings:
    state: Settings = request.app.state.settings
    return state


def _resolve(
    settings: Settings,
    rag: str | None,
    searcher: str | None,
    strategy: str | None,
    embedder: str | None,
    k: int | None,
) -> ResolvedConfig:
    return ResolvedConfig(
        rag=rag or settings.rag,
        searcher=searcher or settings.searcher,
        strategy=strategy or settings.chunker,
        embedder=embedder or settings.embedding_provider,
        k=k or settings.retrieval_k,
    )


def _retrieve(
    settings: Settings,
    config: ResolvedConfig,
    query: str,
    course: str | None,
    lab_id: str | None,
    kinds: list[str] | None = None,
) -> RetrievedContext:
    """Build the pipeline and run one retrieval; every failure surfaces as an HTTP error."""
    from rag_lab_generator.retrieval.searchers.base import SearchFilters

    deps.ensure_chunker(config.strategy)
    pipeline = deps.build_pipeline(settings, config.rag, config.searcher, config.embedder)
    filters = SearchFilters(strategy=config.strategy, course=course, lab_id=lab_id, kinds=kinds)
    with deps.translate(f"retrieval with {config.rag}/{config.searcher}"):
        context: RetrievedContext = pipeline.retrieve(query, config.k, filters)
        return context


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(body: RetrieveRequest, request: Request) -> RetrieveResponse:
    """Run one query through the selected rag strategy and return the retrieved context."""
    settings = settings_of(request)
    config = _resolve(settings, body.rag, body.searcher, body.strategy, body.embedder, body.k)
    started = perf_counter()
    context = await run_in_threadpool(
        _retrieve, settings, config, body.query, body.course, body.lab_id, body.kinds
    )
    return RetrieveResponse(
        config=config,
        latency_ms=round((perf_counter() - started) * 1000, 3),
        context=context,
    )


@router.post("/retrieve/compare", response_model=CompareResponse)
async def compare(body: CompareRequest, request: Request) -> CompareResponse:
    """Run the same query through several rag/searcher pairs, one after another."""
    settings = settings_of(request)
    deps.ensure_chunker(body.strategy or settings.chunker)
    results: list[CompareResult] = []
    for entry in body.configs:
        config = _resolve(settings, entry.rag, entry.searcher, body.strategy, body.embedder, body.k)
        started = perf_counter()
        try:
            context = await run_in_threadpool(
                _retrieve, settings, config, body.query, body.course, body.lab_id, None
            )
            error = None
        except HTTPException as exc:
            context, error = None, str(exc.detail)
        results.append(
            CompareResult(
                config=config,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                context=context,
                error=error,
            )
        )
    return CompareResponse(query=body.query, results=results)


@router.get("/strategies", response_model=StrategiesResponse)
def strategies(request: Request) -> StrategiesResponse:
    """Registered names per component kind plus the defaults coming from Settings."""
    settings = settings_of(request)
    return StrategiesResponse(
        kinds=deps.available_strategies(),
        defaults={
            "rag": settings.rag,
            "searcher": settings.searcher,
            "chunker": settings.chunker,
            "embedder": settings.embedding_provider,
            "llm": settings.llm_provider,
            "k": str(settings.retrieval_k),
        },
    )
