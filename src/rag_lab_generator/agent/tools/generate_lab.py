"""
Role:   Agent tool that writes a new laboratory task in the style of the existing ones.
Input:  Tool arguments (topic, course, reference labs, difficulty), the agent state filters,
        a RagFactory, an LLM and Settings.
Output: A BaseTool returning the rendered lab markdown plus a Sources line, and a ToolArtifact
        carrying the GeneratedLab and the RetrievedContext.
Flow:   Resolve the course from the argument, the state filter or the reference lab ids,
        retrieve reference material for the topic, render the generate_lab prompt, ask the LLM
        (structured output when the provider supports it, markdown otherwise), parse the answer
        into GeneratedLab, render it back to markdown and append the chunk ids used.
"""

import json
from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from rag_lab_generator.agent.rag_factory import RagFactory, RagUnavailableError
from rag_lab_generator.agent.state import AgentState, ToolArtifact
from rag_lab_generator.agent.tools.context import (
    context_text,
    course_of,
    resolve_course,
    resolve_filters,
    retrieve,
    sources_line,
    unavailable_message,
)
from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.generation.prompts import load_prompt
from rag_lab_generator.generation.schemas import (
    LabDraft,
    draft_to_lab,
    parse_lab_markdown,
    render_lab,
)
from rag_lab_generator.models import Course, GeneratedLab, LLMMessage

_NO_STATE: AgentState = {"messages": []}


@runtime_checkable
class StructuredLLM(Protocol):
    """Providers that can fill a pydantic model directly (the Claude SDK parse path)."""

    def complete_structured(
        self,
        messages: list[LLMMessage],
        output_format: type[LabDraft],
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LabDraft: ...


def make_tool(rag_factory: RagFactory, llm: LLM, settings: Settings) -> BaseTool:
    """Build the generate_lab tool bound to one retrieval stack and one LLM."""

    @tool("generate_lab", response_format="content_and_artifact")
    def generate_lab(
        topic: str,
        course: Literal["sop1", "sop2"] | None = None,
        based_on: list[str] | None = None,
        difficulty: Literal["easy", "medium", "hard"] = "medium",
        state: Annotated[AgentState, InjectedState] = _NO_STATE,
    ) -> tuple[str, ToolArtifact]:
        """Write a new SOP laboratory task about `topic`, in the style and difficulty of the
        existing labs. `based_on` lists reference lab ids (for example sop1/l5_fifo) whose style
        and APIs the new task must follow. Leave `course` unset unless the user named one: the
        course the session is filtered by is used then. Returns the task as markdown with
        Description and Stages sections."""
        references = list(based_on or [])
        query = " ".join([topic, *references, "example task stages"])
        data = dict(state)
        selected = resolve_course(data, course, references)
        try:
            filters, k = resolve_filters(settings, data, course=selected)
            context = retrieve(rag_factory, settings, query, filters, k)
        except RagUnavailableError as exc:
            return unavailable_message("generate_lab", exc), ToolArtifact(tool="generate_lab")
        # without any course filter the retrieved material decides which course this lab is for
        target = Course(selected) if selected is not None else course_of(context)
        prompt = load_prompt(
            "generate_lab",
            topic=topic,
            course=target.value,
            difficulty=difficulty,
            based_on=", ".join(references) or "none given, pick the closest labs in the context",
            context=context_text(context),
        )
        lab = _generate(llm, settings, prompt, target, references, difficulty)
        content = f"{render_lab(lab)}\n{sources_line(context)}"
        return content, ToolArtifact(tool="generate_lab", context=context, lab=lab)

    return generate_lab


def _generate(
    llm: LLM,
    settings: Settings,
    prompt: str,
    course: Course,
    based_on: list[str],
    difficulty: str,
) -> GeneratedLab:
    system = load_prompt("system_agent")
    messages = [LLMMessage(role="user", content=prompt)]
    # providers with native structured output fill LabDraft directly; the rest return markdown
    if isinstance(llm, StructuredLLM):
        draft = llm.complete_structured(messages, output_format=LabDraft, system=system)
        return draft_to_lab(draft, course, based_on, difficulty)
    text = llm.complete(messages, system=system, max_tokens=settings.llm_max_tokens).text
    as_json = _as_draft(text)
    if as_json is not None:
        return draft_to_lab(as_json, course, based_on, difficulty)
    return parse_lab_markdown(
        text,
        course=course,
        based_on=based_on,
        difficulty=difficulty,
        fallback_title=f"Generated lab: {course.value}",
    )


def _as_draft(text: str) -> LabDraft | None:
    """Accept a bare or fenced JSON object when the model chose to answer with JSON."""
    body = text.strip()
    if body.startswith("```"):
        body = body.split("```")[1].removeprefix("json").strip()
    if not body.startswith("{"):
        return None
    try:
        data: Any = json.loads(body)
        return LabDraft.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None
