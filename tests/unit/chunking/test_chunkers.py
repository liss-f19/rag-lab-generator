"""
Role:   Unit tests for the invariants every chunker must satisfy plus the fixed-window specifics.
Input:  `settings` and `sample_documents` fixtures from tests/conftest.py.
Output: Assertions; no side effects.
Flow:   Runs each registered chunker over the sample corpus and checks ids, idx, text and kinds;
        then checks the sliding-window overlap and the lab task / code chunks of `fixed`.
"""

import pytest

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    ChunkKind,
    Course,
    Document,
    DocumentKind,
    LabDocument,
    Section,
)
from rag_lab_generator.registry import create

CHUNKERS = ["fixed", "hierarchical", "semantic"]


def test_every_chunker_is_registered() -> None:
    assert set(CHUNKERS).issubset(registry.available("chunker"))


@pytest.mark.parametrize("name", CHUNKERS)
def test_chunk_invariants(name: str, settings: Settings, sample_documents: list[Document]) -> None:
    chunker = create("chunker", name, settings=settings)
    for doc in sample_documents:
        chunks = chunker.chunk(doc)
        assert chunks, f"{name} produced no chunks for {doc.id}"
        assert [c.idx for c in chunks] == list(range(len(chunks)))
        assert [c.id for c in chunks] == [f"{name}:{doc.id}:{i}" for i in range(len(chunks))]
        assert len({c.id for c in chunks}) == len(chunks)
        for chunk in chunks:
            assert chunk.text.strip()
            assert chunk.char_count == len(chunk.text)
            assert chunk.strategy == name
            assert chunk.document_id == doc.id
            assert chunk.course == doc.course


@pytest.mark.parametrize("name", CHUNKERS)
def test_document_kind_drives_chunk_kind(
    name: str, settings: Settings, sample_documents: list[Document]
) -> None:
    expected = {
        DocumentKind.LAB: ChunkKind.TUTORIAL,
        DocumentKind.LECTURE_PDF: ChunkKind.LECTURE,
        DocumentKind.COURSE_INFO: ChunkKind.INFO,
    }
    chunker = create("chunker", name, settings=settings)
    for doc in sample_documents:
        extras = (ChunkKind.TASK, ChunkKind.CODE)
        kinds = {c.kind for c in chunker.chunk(doc) if c.kind not in extras}
        assert kinds == {expected[doc.kind]}


@pytest.mark.parametrize("name", CHUNKERS)
def test_lab_extras_are_chunked(name: str, settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", name, settings=settings).chunk(sample_lab)
    task_ids = {c.metadata["task_id"] for c in chunks if c.kind == ChunkKind.TASK}
    refs = {c.metadata["ref"] for c in chunks if c.kind == ChunkKind.CODE}
    assert task_ids == {"example1", "example2"}
    assert refs == {"src/prog1.c", "src/Makefile"}


@pytest.mark.parametrize("name", CHUNKERS)
def test_lab_chunks_carry_lab_id(name: str, settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", name, settings=settings).chunk(sample_lab)
    assert {c.lab_id for c in chunks} == {sample_lab.id}


def test_fixed_window_overlap(settings: Settings) -> None:
    small = settings.model_copy(update={"chunk_size": 200, "chunk_overlap_ratio": 0.1})
    doc = Document(
        id="sop1/info/plain",
        course=Course.SOP1,
        kind=DocumentKind.COURSE_INFO,
        title="plain",
        sections=[Section(id="s", title="s", text="abcdefghij" * 100)],
    )
    chunks = create("chunker", "fixed", settings=small).chunk(doc)
    assert len(chunks) > 1
    overlap = int(200 * 0.1)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert len(previous.text) <= 200
        assert current.text[:overlap] == previous.text[-overlap:]


def test_fixed_prefers_blank_line_boundaries(settings: Settings) -> None:
    small = settings.model_copy(update={"chunk_size": 300})
    paragraph = "word " * 20
    doc = Document(
        id="sop1/info/paragraphs",
        course=Course.SOP1,
        kind=DocumentKind.COURSE_INFO,
        title="paragraphs",
        sections=[Section(id="s", title="s", text="\n\n".join([paragraph.strip()] * 8))],
    )
    chunks = create("chunker", "fixed", settings=small).chunk(doc)
    assert all(chunk.text.endswith("word") for chunk in chunks)


def test_fixed_splits_long_code_files(settings: Settings, sample_lab: LabDocument) -> None:
    tiny = settings.model_copy(update={"chunk_size": 40})
    chunks = create("chunker", "fixed", settings=tiny).chunk(sample_lab)
    code = [c for c in chunks if c.kind == ChunkKind.CODE and c.metadata["ref"] == "src/prog1.c"]
    assert len(code) > 1
    assert "".join(c.text for c in code) == sample_lab.code_files[0].content
