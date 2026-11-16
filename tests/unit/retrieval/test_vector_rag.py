"""
Role:   Unit tests for the vector RAG strategy: dedupe, parent expansion and trace.
Input:  `settings` fixture; a stub searcher and a stub store, so no database is touched.
Output: Assertions; no side effects.
Flow:   Feeds canned ScoredChunks through VectorRAG and checks that duplicates disappear, that
        missing parents are appended with a damped score and that the trace carries the timings.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, ChunkKind, Course, ScoredChunk
from rag_lab_generator.registry import create
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

FILTERS = SearchFilters(strategy="hierarchical")


def _chunk(idx: int, parent_id: str | None = None) -> Chunk:
    return Chunk(
        id=f"hierarchical:doc:{idx}",
        document_id="doc",
        course=Course.SOP1,
        kind=ChunkKind.TUTORIAL,
        strategy="hierarchical",
        idx=idx,
        text=f"chunk {idx}",
        parent_id=parent_id,
        section_id=f"s{idx}",
    )


class StubStore(PostgresStore):
    """Chunk store backed by a dict; fetch_chunks is the only method the RAG layer calls."""

    def __init__(self, settings: Settings, chunks: list[Chunk]) -> None:
        super().__init__(settings)
        self.chunks = {chunk.id: chunk for chunk in chunks}

    def fetch_chunks(self, ids: list[str]) -> dict[str, Chunk]:
        return {chunk_id: self.chunks[chunk_id] for chunk_id in ids if chunk_id in self.chunks}


class StubSearcher(Searcher):
    name = "stub"

    def __init__(self, results: list[ScoredChunk]) -> None:
        self.results = results

    def search(self, query: str, k: int, filters: SearchFilters) -> list[ScoredChunk]:
        return self.results[:k]


def _rag(settings: Settings, results: list[ScoredChunk], stored: list[Chunk]) -> RAG:
    rag: RAG = create(
        "rag",
        "vector",
        searcher=StubSearcher(results),
        store=StubStore(settings, stored),
        settings=settings,
    )
    return rag


def test_parent_chunk_is_appended_with_a_lower_score(settings: Settings) -> None:
    parent = _chunk(0)
    child = _chunk(1, parent_id=parent.id)
    rag = _rag(settings, [ScoredChunk(chunk=child, score=0.8, source="stub")], [parent, child])
    context = rag.retrieve("query", 5, FILTERS)
    assert [sc.chunk.id for sc in context.chunks] == [child.id, parent.id]
    assert context.chunks[1].score < context.chunks[0].score
    assert context.chunks[1].source == "parent_expansion"


def test_present_parent_is_not_duplicated(settings: Settings) -> None:
    parent = _chunk(0)
    child = _chunk(1, parent_id=parent.id)
    results = [
        ScoredChunk(chunk=child, score=0.8, source="stub"),
        ScoredChunk(chunk=parent, score=0.7, source="stub"),
    ]
    rag = _rag(settings, results, [parent, child])
    context = rag.retrieve("query", 5, FILTERS)
    assert [sc.chunk.id for sc in context.chunks] == [child.id, parent.id]
    assert context.chunks[1].source == "stub"


def test_duplicate_hits_are_deduplicated(settings: Settings) -> None:
    chunk = _chunk(1)
    results = [
        ScoredChunk(chunk=chunk, score=0.9, source="stub"),
        ScoredChunk(chunk=chunk, score=0.4, source="stub"),
    ]
    rag = _rag(settings, results, [chunk])
    context = rag.retrieve("query", 5, FILTERS)
    assert len(context.chunks) == 1
    assert context.chunks[0].score == 0.9


def test_trace_reports_searcher_and_latency(settings: Settings) -> None:
    chunk = _chunk(1)
    rag = _rag(settings, [ScoredChunk(chunk=chunk, score=0.5, source="stub")], [chunk])
    context = rag.retrieve("query", 3, FILTERS)
    assert context.rag == "vector"
    assert context.trace["searcher"] == "stub"
    assert context.trace["k"] == 3
    assert context.trace["latency_ms"] >= 0.0


def test_missing_parent_is_skipped(settings: Settings) -> None:
    child = _chunk(1, parent_id="hierarchical:doc:999")
    rag = _rag(settings, [ScoredChunk(chunk=child, score=0.5, source="stub")], [child])
    context = rag.retrieve("query", 3, FILTERS)
    assert [sc.chunk.id for sc in context.chunks] == [child.id]
