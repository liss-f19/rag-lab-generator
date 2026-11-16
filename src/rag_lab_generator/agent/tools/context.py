"""
Role:   Shared retrieval helpers used by every agent tool.
Input:  A RagFactory, Settings, the agent state and the query of the current tool call.
Output: RetrievedContext plus the rendered context text and the Sources line, or a clear
        RagUnavailableError message when retrieval is impossible.
Flow:   resolve_course() prefers the explicit tool argument, then the filter carried by the
        state, then the course prefix of the reference lab ids; resolve_filters() merges that
        with the lab and k overrides stored in the state;
        retrieve() calls the RAG through the factory and turns any failure into
        RagUnavailableError; sources_line() lists the chunk ids that were actually used.
"""

from typing import Any

from rag_lab_generator.agent.rag_factory import SETUP_HINT, RagFactory, RagUnavailableError
from rag_lab_generator.config import Settings
from rag_lab_generator.models import Course, RetrievedContext
from rag_lab_generator.retrieval.searchers.base import SearchFilters

CONTEXT_MAX_CHARS = 12000
NO_CONTEXT = "(no course material retrieved)"
COURSES = (Course.SOP1.value, Course.SOP2.value)


def resolve_course(
    state: dict[str, Any] | None,
    course: str | None = None,
    based_on: list[str] | None = None,
) -> str | None:
    """Pick the course: explicit argument, then the state filter, then the reference lab ids."""
    if course in COURSES:
        return course
    stated = (state or {}).get("course")
    if isinstance(stated, str) and stated in COURSES:
        return stated
    # lab ids look like sop2/l3_threads, so their prefix names the course
    for lab_id in based_on or []:
        prefix = lab_id.split("/")[0]
        if prefix in COURSES:
            return prefix
    return None


def course_of(context: RetrievedContext, fallback: Course = Course.SOP1) -> Course:
    """Read the course from the best ranked chunk when no filter told us which one it is."""
    for scored in context.chunks:
        if scored.chunk.course.value in COURSES:
            return scored.chunk.course
    return fallback


def resolve_filters(
    settings: Settings,
    state: dict[str, Any] | None,
    course: str | None = None,
    lab_id: str | None = None,
) -> tuple[SearchFilters, int]:
    """Combine tool arguments with the course/lab/k overrides carried by the agent state."""
    data = state or {}
    filters = SearchFilters(
        strategy=settings.chunker,
        course=course,
        lab_id=lab_id or data.get("lab_id"),
    )
    k = data.get("retrieval_k") or settings.retrieval_k
    return filters, int(k)


def retrieve(
    rag_factory: RagFactory,
    settings: Settings,
    query: str,
    filters: SearchFilters,
    k: int,
) -> RetrievedContext:
    """Run one retrieval; every failure becomes a RagUnavailableError with a fix hint."""
    rag = rag_factory()
    try:
        context = rag.retrieve(query, k=k, filters=filters)
    except RagUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 - a broken store must not crash the agent
        raise RagUnavailableError(f"retrieval failed ({exc}); {SETUP_HINT}") from exc
    if not context.chunks:
        raise RagUnavailableError(
            f"no chunks indexed for strategy {filters.strategy!r} "
            f"(course={filters.course}, lab={filters.lab_id}); {SETUP_HINT}"
        )
    return context


def context_text(context: RetrievedContext, max_chars: int = CONTEXT_MAX_CHARS) -> str:
    text = context.as_prompt_text(max_chars=max_chars)
    return text or NO_CONTEXT


def sources_line(context: RetrievedContext) -> str:
    """Render the chunk ids used for an answer so the student can verify them."""
    ids = [scored.chunk.id for scored in context.chunks]
    return "Sources: " + (", ".join(ids) if ids else "none")


def unavailable_message(tool: str, exc: RagUnavailableError) -> str:
    return f"The knowledge base is unavailable for `{tool}`: {exc}"
