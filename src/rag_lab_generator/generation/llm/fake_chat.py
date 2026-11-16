"""
Role:   Offline LangChain chat model that replays a scripted sequence of AI messages.
Input:  A list of AIMessage objects (some carrying tool_calls) given at construction time.
Output: One scripted AIMessage per invocation, then a fixed final message once the script ends.
Flow:   _generate() pops the next scripted message, copies it and wraps it in a ChatResult;
        with an exhausted script it echoes the last tool result, or picks one bound tool by
        keyword so the whole agent loop can be demonstrated offline; bind_tools() records the
        bound tools and returns the same instance.
"""

from collections.abc import Callable, Sequence
from typing import Any, cast

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field

TOOL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "generate_lab": ("generate", "new lab", "task", "zadanie", "wygeneruj"),
    "visualize_concept": ("diagram", "visuali", "mermaid", "draw", "narysuj"),
    "explain_topic": ("explain", "what is", "how does", "wyjas", "wytlumacz"),
}


class ScriptedFakeChatModel(BaseChatModel):
    """Deterministic chat model used by the agent tests and by the `fake` LLM provider."""

    script: list[AIMessage] = Field(default_factory=list)
    final_text: str = "[fake-llm] done"
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[Any] = Field(default_factory=list)
    cursor: int = 0
    auto_tool_call: bool = True

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        message = self._next_message(messages)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        self.bound_tools = list(tools)
        return cast(Runnable[LanguageModelInput, AIMessage], self)

    @property
    def bound_tool_names(self) -> list[str]:
        return [getattr(tool, "name", str(tool)) for tool in self.bound_tools]

    def _next_message(self, messages: list[BaseMessage]) -> AIMessage:
        # replay the script first; it drives the tool calls the agent tests assert on
        if self.cursor < len(self.script):
            message = self.script[self.cursor].model_copy(deep=True)
            self.cursor += 1
            return message
        # a finished tool call ends the turn: report what the tool produced
        if messages and isinstance(messages[-1], ToolMessage):
            return AIMessage(content=str(messages[-1].content))
        tool_call = self._pick_tool(messages)
        if tool_call is not None:
            return tool_call
        return AIMessage(content=self.final_text)

    def _pick_tool(self, messages: list[BaseMessage]) -> AIMessage | None:
        """Route the user question to one bound tool by keyword so the graph can be demoed."""
        if not self.auto_tool_call or not self.bound_tools:
            return None
        question = next(
            (str(m.content) for m in reversed(messages) if isinstance(m, HumanMessage)), ""
        )
        available = self.bound_tool_names
        lowered = question.lower()
        for name, keywords in TOOL_KEYWORDS.items():
            if name in available and any(word in lowered for word in keywords):
                return AIMessage(
                    content="",
                    tool_calls=[
                        {"name": name, "args": _tool_args(name, question), "id": "fake-call-1"}
                    ],
                )
        return None


def _tool_args(name: str, question: str) -> dict[str, Any]:
    # never pass a course: the filter carried by the agent state must win
    if name == "generate_lab":
        return {"topic": question}
    if name == "visualize_concept":
        return {"concept": question}
    return {"topic": question}
