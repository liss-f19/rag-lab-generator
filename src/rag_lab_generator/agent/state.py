"""
Role:   LangGraph state schema shared by the agent graph, its tools and the CLI.
Input:  Messages appended by the model and the tool node; filters set by the caller.
Output: AgentState mapping passed through every node of the graph.
Flow:   Extends the prebuilt ReAct state (messages with the add_messages reducer plus
        remaining_steps) with the course/lab filters and retrieval overrides the tools read,
        and with the last retrieval result and the last generated lab for the caller.
"""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.prebuilt.chat_agent_executor import AgentState as ReActState
from pydantic import BaseModel, ValidationError

from rag_lab_generator.models import GeneratedLab, RetrievedContext


class ToolArtifact(BaseModel):
    """Side channel a tool attaches to its ToolMessage so the caller keeps the typed result."""

    tool: str
    context: RetrievedContext | None = None
    lab: GeneratedLab | None = None


class AgentState(ReActState, total=False):
    """ReAct state plus the retrieval filters and the artifacts produced by the tools."""

    course: str | None
    lab_id: str | None
    rag: str | None
    retrieval_k: int | None
    last_context: RetrievedContext | None
    generated: GeneratedLab | None


def initial_state(
    message: BaseMessage,
    course: str | None = None,
    lab_id: str | None = None,
    rag: str | None = None,
    retrieval_k: int | None = None,
) -> AgentState:
    """Build the input state for one agent turn."""
    return AgentState(
        messages=[message],
        course=course,
        lab_id=lab_id,
        rag=rag,
        retrieval_k=retrieval_k,
        last_context=None,
        generated=None,
    )


def last_answer(state: dict[str, Any]) -> str:
    """Return the text of the final assistant message of a finished run."""
    for message in reversed(list(state.get("messages", []))):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return _as_text(message.content)
    return ""


def last_generated_lab(state: dict[str, Any]) -> GeneratedLab | None:
    """Recover the GeneratedLab a tool attached to its ToolMessage artifact."""
    stored = _as_model(state.get("generated"), GeneratedLab)
    if stored is not None:
        return stored
    for artifact in _artifacts(state):
        if artifact.lab is not None:
            return artifact.lab
    return None


def last_retrieved_context(state: dict[str, Any]) -> RetrievedContext | None:
    """Recover the RetrievedContext of the most recent tool call."""
    stored = _as_model(state.get("last_context"), RetrievedContext)
    if stored is not None:
        return stored
    for artifact in _artifacts(state):
        if artifact.context is not None:
            return artifact.context
    return None


def _artifacts(state: dict[str, Any]) -> list[ToolArtifact]:
    # newest first; the checkpointer stores artifacts as plain dicts, so revalidate them
    found: list[ToolArtifact] = []
    for message in reversed(list(state.get("messages", []))):
        if not isinstance(message, ToolMessage):
            continue
        artifact = _as_model(message.artifact, ToolArtifact)
        if artifact is not None:
            found.append(artifact)
    return found


def _as_model[ModelT: BaseModel](value: Any, model: type[ModelT]) -> ModelT | None:
    if isinstance(value, model):
        return value
    if isinstance(value, dict):
        try:
            return model.model_validate(value)
        except ValidationError:
            return None
    return None


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)
