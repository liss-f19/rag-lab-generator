"""
Role:   Agent tool that draws a Mermaid diagram of a course mechanism.
Input:  Tool arguments (concept, diagram type, optional course), the agent state filters, a
        RagFactory, an LLM and Settings.
Output: A BaseTool returning a ```mermaid block with a short legend plus a Sources line, and a
        ToolArtifact with the RetrievedContext behind it.
Flow:   Retrieve material about the concept, render the visualize_concept prompt, ask the LLM
        and wrap the answer in a mermaid fence when the model did not fence it itself.
"""

from typing import Annotated, Literal

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from rag_lab_generator.agent.rag_factory import RagFactory, RagUnavailableError
from rag_lab_generator.agent.state import AgentState, ToolArtifact
from rag_lab_generator.agent.tools.context import (
    context_text,
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

DEFAULT_NODES = {
    "flowchart": "flowchart TD\n    A[concept] --> B[not enough material]",
    "sequenceDiagram": "sequenceDiagram\n    participant P\n    P->>P: not enough material",
    "stateDiagram": "stateDiagram-v2\n    [*] --> unknown",
}


def make_tool(rag_factory: RagFactory, llm: LLM, settings: Settings) -> BaseTool:
    """Build the visualize_concept tool bound to one retrieval stack and one LLM."""

    @tool("visualize_concept", response_format="content_and_artifact")
    def visualize_concept(
        concept: str,
        diagram_type: Literal["flowchart", "sequenceDiagram", "stateDiagram"] = "flowchart",
        course: Literal["sop1", "sop2"] | None = None,
        state: Annotated[AgentState, InjectedState] = _NO_STATE,
    ) -> tuple[str, ToolArtifact]:
        """Draw a Mermaid diagram of an Operating Systems mechanism (fork/exec/wait lifecycle,
        pipe data flow, epoll loop, signal delivery, thread synchronisation). Returns one mermaid
        code block and a short legend. Leave `course` unset unless the user named one: the course
        the session is filtered by is used then."""
        data = dict(state)
        try:
            filters, k = resolve_filters(settings, data, course=resolve_course(data, course))
            context = retrieve(rag_factory, settings, concept, filters, k)
        except RagUnavailableError as exc:
            return (
                unavailable_message("visualize_concept", exc),
                ToolArtifact(tool="visualize_concept"),
            )
        prompt = load_prompt(
            "visualize_concept",
            concept=concept,
            diagram_type=diagram_type,
            context=context_text(context),
        )
        answer = llm.complete(
            [LLMMessage(role="user", content=prompt)],
            system=load_prompt("system_agent"),
            max_tokens=settings.llm_max_tokens,
        ).text
        content = f"{_as_mermaid(answer, diagram_type)}\n\n{sources_line(context)}"
        return content, ToolArtifact(tool="visualize_concept", context=context)

    return visualize_concept


def _as_mermaid(answer: str, diagram_type: str) -> str:
    """Guarantee a mermaid fence even when the provider answered with plain text."""
    text = answer.strip()
    if "```mermaid" in text:
        return text
    body = text if text.startswith(tuple(DEFAULT_NODES)) else DEFAULT_NODES[diagram_type]
    legend = "" if body is text else f"\n\n{text}"
    return f"```mermaid\n{body}\n```{legend}"
