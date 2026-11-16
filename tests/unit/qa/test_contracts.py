"""
Role:   QA contract tests for the shared models, the registry and the fake LLM.
Input:  rag_lab_generator.models, registry and the "fake" llm strategy; the `settings` fixture.
Output: pytest assertions on prompt rendering, filter construction and LLM determinism.
Flow:   Builds RetrievedContext objects by hand and checks as_prompt_text cutoff behaviour,
        constructs SearchFilters with and without kinds, and calls the fake LLM twice with the
        same input to assert a deterministic, non-empty answer.
"""

import pytest

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    LLMMessage,
    RetrievedContext,
    ScoredChunk,
)
from rag_lab_generator.retrieval.searchers.base import SearchFilters


def _chunk(idx: int, text: str, section_id: str | None = None) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            id=f"qa:doc:{idx}",
            document_id="sop1/lab/l1_filesystem",
            course=Course.SOP1,
            kind=ChunkKind.TUTORIAL,
            strategy="qa",
            idx=idx,
            text=text,
            section_id=section_id,
        ),
        score=1.0 / (idx + 1),
        source="qa",
    )


def _context(*chunks: ScoredChunk) -> RetrievedContext:
    return RetrievedContext(query="q", rag="vector", chunks=list(chunks))


def test_chunk_char_count_is_filled_automatically() -> None:
    chunk = _chunk(0, "abcde").chunk
    assert chunk.char_count == 5


def test_as_prompt_text_includes_every_chunk_without_limit() -> None:
    text = _context(_chunk(0, "alpha"), _chunk(1, "beta")).as_prompt_text()
    assert "alpha" in text
    assert "beta" in text
    assert text.count("---") == 1


def test_as_prompt_text_labels_use_section_id_then_kind() -> None:
    text = _context(_chunk(0, "alpha", section_id="browsing"), _chunk(1, "beta")).as_prompt_text()
    assert "/ browsing]" in text
    assert "/ tutorial]" in text


def test_as_prompt_text_respects_max_chars() -> None:
    """The cutoff drops whole blocks; the result must stay under the budget."""
    context = _context(_chunk(0, "a" * 200), _chunk(1, "b" * 200), _chunk(2, "c" * 200))
    limited = context.as_prompt_text(max_chars=300)
    assert len(limited) <= 300
    assert "a" * 200 in limited
    assert "b" * 200 not in limited


def test_as_prompt_text_zero_budget_yields_empty_string() -> None:
    assert _context(_chunk(0, "alpha")).as_prompt_text(max_chars=0) == ""


def test_as_prompt_text_on_empty_context() -> None:
    assert _context().as_prompt_text() == ""
    assert _context().as_prompt_text(max_chars=10) == ""


def test_search_filters_defaults_and_kinds() -> None:
    bare = SearchFilters(strategy="hierarchical")
    assert bare.course is None and bare.lab_id is None and bare.kinds is None
    filtered = SearchFilters(
        strategy="hierarchical",
        course=Course.SOP2.value,
        lab_id="sop2/lab/l7_sockets_epoll",
        kinds=[ChunkKind.TASK.value, ChunkKind.CODE.value],
    )
    assert filtered.kinds == ["task", "code"]


def test_search_filters_requires_strategy() -> None:
    with pytest.raises(ValueError):
        SearchFilters()  # type: ignore[call-arg]


def test_fake_llm_is_deterministic(settings: Settings) -> None:
    llm = registry.create("llm", "fake", settings=settings)
    messages = [LLMMessage(role="user", content="explain what a zombie process is")]
    first = llm.complete(messages, system="you are a tutor")
    second = llm.complete(messages, system="you are a tutor")
    assert first.text == second.text
    assert first.text.strip()
    assert first.model == second.model


def test_fake_llm_reacts_to_the_prompt(settings: Settings) -> None:
    llm = registry.create("llm", "fake", settings=settings)
    a = llm.complete([LLMMessage(role="user", content="alpha question")])
    b = llm.complete([LLMMessage(role="user", content="beta question")])
    assert a.text != b.text, "fake LLM ignores its input; retrieval bugs would stay invisible"


def test_registry_create_rejects_unknown_kind() -> None:
    with pytest.raises(registry.UnknownStrategyError):
        registry.get("chunker", "nonexistent")
