"""
Role:   Shared fixtures for the agent tests: offline settings, in-memory chunks and stub RAGs.
Input:  none
Output: Settings, StubRAG and FailingRAG instances used by the tool and graph tests.
Flow:   default_chunks() builds two Chunk models of one lab of the given course; StubRAG
        returns them as a
        RetrievedContext and records every call; FailingRAG raises the way a missing table does.
"""

from typing import Any

import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, ChunkKind, Course, RetrievedContext, ScoredChunk
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import SearchFilters

CHUNK_TEXTS = {
    "hierarchical:sop1/l5_fifo:0": "mkfifo(const char *path, mode_t mode) creates a named pipe.",
    "hierarchical:sop1/l5_fifo:1": "Example task 1: write a program reading from a FIFO.",
}


class StubRAG(RAG):
    """RAG replacement that answers from in-memory chunks and records every call."""

    name = "stub"

    def __init__(self, settings: Settings, chunks: list[Chunk] | None = None) -> None:
        self.settings = settings
        self.chunks = chunks if chunks is not None else default_chunks()
        self.calls: list[dict[str, Any]] = []

    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext:
        self.calls.append({"query": query, "k": k, "filters": filters})
        scored = [
            ScoredChunk(chunk=chunk, score=1.0 - i / 10, source="stub")
            for i, chunk in enumerate(self.chunks[:k])
        ]
        return RetrievedContext(query=query, rag="stub", chunks=scored, trace={"stub": True})


class FailingRAG(RAG):
    """RAG replacement that raises the way an empty or unreachable store would."""

    name = "failing"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext:
        raise RuntimeError("relation 'chunks' does not exist")


def default_chunks(course: Course = Course.SOP1) -> list[Chunk]:
    lab_id = f"{course.value}/l5_fifo"
    return [
        Chunk(
            id=chunk_id.replace("sop1", course.value),
            document_id=lab_id,
            course=course,
            lab_id=lab_id,
            kind=ChunkKind.TUTORIAL if idx == 0 else ChunkKind.TASK,
            strategy="hierarchical",
            idx=idx,
            text=text,
            section_id="named-pipes",
        )
        for idx, (chunk_id, text) in enumerate(CHUNK_TEXTS.items())
    ]


@pytest.fixture
def settings() -> Settings:
    return Settings(llm_provider="fake", retrieval_k=4, chunker="hierarchical")


@pytest.fixture
def stub_rag(settings: Settings) -> StubRAG:
    return StubRAG(settings)
