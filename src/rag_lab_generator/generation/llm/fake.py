"""
Role:   Deterministic offline LLM used when no API key is configured and in tests.
Input:  Settings; an optional canned answer and an optional scripted AIMessage sequence.
Output: LLMResponse echoing a canned answer that embeds the last user message.
Flow:   complete() builds a short deterministic string; to_langchain() returns a
        ScriptedFakeChatModel replaying the script (or the canned answer) so the agent
        graph, including tool calls, can run without network.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.generation.llm.fake_chat import ScriptedFakeChatModel
from rag_lab_generator.models import LLMMessage, LLMResponse
from rag_lab_generator.registry import register


@register("llm", "fake")
class FakeLLM(LLM):
    name = "fake"

    def __init__(
        self,
        settings: Settings,
        canned: str | None = None,
        script: list[AIMessage] | None = None,
    ) -> None:
        super().__init__(settings)
        self.canned = canned
        self.script = script or []
        self.chat_model = ScriptedFakeChatModel(
            script=self.script,
            final_text=self.canned or "[fake-llm] done",
        )

    def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        last = messages[-1].content if messages else ""
        text = self.canned or f"[fake-llm] {last[:200]}"
        return LLMResponse(
            text=text,
            model="fake",
            input_tokens=len(last) // 4,
            output_tokens=len(text) // 4,
            stop_reason="end_turn",
        )

    def to_langchain(self) -> BaseChatModel:
        return self.chat_model
