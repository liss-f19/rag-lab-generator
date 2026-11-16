"""
Role:   QA robustness tests: every chunker survives degenerate documents and keeps its id contract.
Input:  The `settings` fixture (fake embedder, small dirs) and hand-built edge-case Documents.
Output: pytest assertions on crash-freedom, contiguous idx and unique ids.
Flow:   Parametrizes over every registered chunker name, feeds each a family of pathological
        documents (empty, whitespace-only, one huge fenced code block, Polish unicode, a section
        ten times the chunk size) and asserts the Chunk invariants documented in chunking/base.py.
"""

from collections.abc import Callable

import pytest

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    Chunk,
    CodeFile,
    Course,
    Document,
    DocumentKind,
    LabDocument,
    Section,
    Stage,
    Task,
)

CHUNKER_NAMES = ["fixed", "hierarchical", "semantic"]


def _doc(doc_id: str, *sections: Section) -> Document:
    return Document(
        id=doc_id,
        course=Course.SOP1,
        kind=DocumentKind.LECTURE_PDF,
        title="edge case",
        sections=list(sections),
    )


def _section(sid: str, text: str, order: int = 0) -> Section:
    return Section(id=sid, title=sid.replace("-", " "), level=2, order=order, text=text)


def empty_document() -> Document:
    return _doc("qa/empty")


def empty_sections_document() -> Document:
    return _doc("qa/empty-sections", _section("a", ""), _section("b", "   \n\n\t ", 1))


def huge_code_block_document() -> Document:
    body = "\n".join(f"    int x{i} = {i};" for i in range(4000))
    return _doc("qa/huge-code", _section("code", f"```c\nint main(void) {{\n{body}\n}}\n```"))


def polish_unicode_document() -> Document:
    text = (
        "Zażółć gęślą jaźń — deskryptory plików w systemie POSIX.\n\n"
        "Funkcja `otwórz()` zwraca liczbę całkowitą. Średnik; myślnik – i „cudzysłów”.\n\n"
        "Emoji w tekście: \U0001f9ea\U0001f4c1. Symbole: ≤ ≥ ∞ → ∀x∈ℕ.\n\n"
    ) * 40
    return _doc("qa/polish", _section("wstęp", text))


def oversized_section_document() -> Document:
    # One section ten times the configured chunk size, with no paragraph breaks at all.
    return _doc("qa/oversized", _section("wall", "lorem ipsum dolor sit amet " * 3000))


def no_newline_document() -> Document:
    return _doc("qa/one-line", _section("line", "x" * 25_000))


def lab_with_empty_task_document() -> LabDocument:
    return LabDocument(
        id="qa/lab/edge",
        course=Course.SOP2,
        kind=DocumentKind.LAB,
        title="Edge lab",
        number="99",
        slug="l99_edge",
        lab_id="qa/lab/edge",
        sections=[_section("intro", ""), _section("body", "readdir and opendir", 1)],
        tasks=[
            Task(id="example1", title="", statement="", stages=[]),
            Task(
                id="example2",
                title="Zadanie",
                statement="Napisz program.",
                stages=[Stage(n=1, text=""), Stage(n=2, text="Zrób coś.")],
                solution_refs=["src/prog1.c"],
            ),
        ],
        code_files=[
            CodeFile(ref="src/prog1.c", lang="c", content=""),
        ],
    )


EDGE_CASES: list[Callable[[], Document]] = [
    empty_document,
    empty_sections_document,
    huge_code_block_document,
    polish_unicode_document,
    oversized_section_document,
    no_newline_document,
    lab_with_empty_task_document,
]


def _assert_chunk_invariants(chunks: list[Chunk], doc: Document, strategy: str) -> None:
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), f"{strategy}/{doc.id}: duplicate chunk ids"
    assert [c.idx for c in chunks] == list(range(len(chunks))), (
        f"{strategy}/{doc.id}: idx not contiguous from 0: {[c.idx for c in chunks]}"
    )
    for chunk in chunks:
        assert chunk.id == f"{strategy}:{doc.id}:{chunk.idx}", (
            f"{strategy}/{doc.id}: id {chunk.id!r} breaks the <strategy>:<document_id>:<idx> rule"
        )
        assert chunk.document_id == doc.id
        assert chunk.strategy == strategy
        assert chunk.char_count == len(chunk.text)
        assert chunk.text.strip(), f"{strategy}/{doc.id}: chunk {chunk.idx} is blank"


@pytest.mark.parametrize("name", CHUNKER_NAMES)
@pytest.mark.parametrize("factory", EDGE_CASES, ids=[f.__name__ for f in EDGE_CASES])
def test_chunker_survives_edge_documents(
    name: str, factory: Callable[[], Document], settings: Settings
) -> None:
    chunker = registry.create("chunker", name, settings=settings)
    doc = factory()
    chunks = chunker.chunk(doc)
    _assert_chunk_invariants(chunks, doc, name)


@pytest.mark.parametrize("name", CHUNKER_NAMES)
def test_chunker_is_deterministic(name: str, settings: Settings) -> None:
    chunker = registry.create("chunker", name, settings=settings)
    doc = polish_unicode_document()
    first = [c.model_dump() for c in chunker.chunk(doc)]
    second = [c.model_dump() for c in chunker.chunk(doc)]
    assert first == second


@pytest.mark.parametrize("name", CHUNKER_NAMES)
def test_chunker_keeps_every_chunk_within_a_sane_size(name: str, settings: Settings) -> None:
    """No chunk may exceed 4x the configured target; the prompt budget depends on it."""
    chunker = registry.create("chunker", name, settings=settings)
    limit = settings.chunk_size * 4
    for factory in EDGE_CASES:
        for chunk in chunker.chunk(factory()):
            assert chunk.char_count <= limit, (
                f"{name}/{factory.__name__}: chunk {chunk.idx} has {chunk.char_count} chars "
                f"(target {settings.chunk_size})"
            )


@pytest.mark.parametrize("name", CHUNKER_NAMES)
def test_chunker_covers_a_normal_lab(
    name: str, settings: Settings, sample_lab: LabDocument
) -> None:
    chunker = registry.create("chunker", name, settings=settings)
    chunks = chunker.chunk(sample_lab)
    assert chunks, f"{name} produced no chunks for a normal lab"
    _assert_chunk_invariants(chunks, sample_lab, name)
    joined = "\n".join(c.text for c in chunks)
    assert "readdir" in joined, f"{name} dropped the tutorial body of the lab"
