"""
Role:   Agent tool that explains one course topic before a laboratory.
Input:  Tool arguments (topic, course, depth), the agent state filters, a RagFactory, an LLM
        and Settings.
Output: A BaseTool returning the explanation plus a Sources line, and a ToolArtifact with the
        RetrievedContext behind it.
Flow:   Resolve the course from the argument or the state filter, retrieve the tutorial and
        lecture fragments about the topic, render the explain_topic prompt, ask the LLM and
        append the chunk ids used.
"""

from typing import Annotated, Literal

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
from rag_lab_generator.models import LLMMessage

_NO_STATE: AgentState = {"messages": []}


def make_tool(rag_factory: RagFactory, llm: LLM, settings: Settings) -> BaseTool:
    """Build the explain_topic tool bound to one retrieval stack and one LLM."""

    @tool("explain_topic", response_format="content_and_artifact")
    def explain_topic(
        topic: str,
        course: Literal["sop1", "sop2"] | None = None,
        depth: Literal["short", "full"] = "full",
        state: Annotated[AgentState, InjectedState] = _NO_STATE,
    ) -> tuple[str, ToolArtifact]:
        """Explain an Operating Systems topic (a POSIX mechanism, a system call, a concept) to a
        student preparing for a laboratory, grounded in the course material: definition, why it
        matters, a minimal C example, common mistakes, man pages and self-check questions. Leave
        `course` unset unless the user named one: the course the session is filtered by is used
        then."""
        data = dict(state)
        selected = resolve_course(data, course)
        try:
            filters, k = resolve_filters(settings, data, course=selected)
            context = retrieve(rag_factory, settings, topic, filters, k)
        except RagUnavailableError as exc:
            return unavailable_message("explain_topic", exc), ToolArtifact(tool="explain_topic")
        prompt = load_prompt(
            "explain_topic",
            topic=topic,
            course=selected or course_of(context).value,
            depth=depth,
            context=context_text(context),
        )
        answer = llm.complete(
            [LLMMessage(role="user", content=prompt)],
            system=load_prompt("system_agent"),
            max_tokens=settings.llm_max_tokens,
        ).text
        content = f"{answer.strip()}\n\n{sources_line(context)}"
        return content, ToolArtifact(tool="explain_topic", context=context)

    return explain_topic
