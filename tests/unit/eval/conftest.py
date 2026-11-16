"""
Role:   Fixtures shared by the eval unit tests: chunk factory and a ranked result builder.
Input:  none
Output: make_chunk / ranked helpers used to hand-build retrieval results.
Flow:   Two module-level factories are exposed as fixtures so every test builds the same shape of
        Chunk and ScoredChunk without touching the database.
"""

import pytest

from rag_lab_generator.models import Chunk, ChunkKind, Course, ScoredChunk


def build_chunk(
    document_id: str,
    idx: int = 0,
    lab_id: str | None = None,
    section_id: str | None = None,
    kind: ChunkKind = ChunkKind.TUTORIAL,
    text: str = "body",
    strategy: str = "hierarchical",
) -> Chunk:
    return Chunk(
        id=f"{strategy}:{document_id}:{idx}",
        document_id=document_id,
        course=Course.SOP1,
        lab_id=lab_id,
        kind=kind,
        strategy=strategy,
        idx=idx,
        text=text,
        section_id=section_id,
    )


def build_ranked(chunks: list[Chunk]) -> list[ScoredChunk]:
    """Wrap chunks into a descending score list, best first."""
    return [
        ScoredChunk(chunk=chunk, score=1.0 - 0.1 * position, source="test")
        for position, chunk in enumerate(chunks)
    ]


@pytest.fixture
def make_chunk():  # type: ignore[no-untyped-def]
    return build_chunk


@pytest.fixture
def ranked():  # type: ignore[no-untyped-def]
    return build_ranked
