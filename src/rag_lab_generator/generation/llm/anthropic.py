"""
Role:   Claude provider for the generation layer; the only place the anthropic SDK is used.
Input:  Settings (model id, max tokens, optional api key); messages and system prompt at call time.
Output: LLMResponse with text and usage; a ChatAnthropic model for the LangGraph agent.
Flow:   The SDK client is built lazily on first call so importing without a key never fails;
        complete() sends one Messages request with adaptive thinking and no sampling params,
        streaming when the requested max_tokens exceeds the non-streaming budget;
        complete_structured() uses messages.parse to fill a pydantic model.
"""

from typing import Any, TypeVar

import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.models import LLMMessage, LLMResponse
from rag_lab_generator.registry import register

NON_STREAMING_MAX_TOKENS = 16000
THINKING: dict[str, str] = {"type": "adaptive"}

T = TypeVar("T", bound=BaseModel)


class LLMCallError(RuntimeError):
    """Raised when the Claude API rejects or cannot serve a request."""


@register("llm", "anthropic")
class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        # build the SDK client on first use; without a key the SDK resolves the env var
        if self._client is None:
            key = self.settings.anthropic_api_key
            self._client = (
                anthropic.Anthropic(api_key=key.get_secret_value())
                if key is not None
                else anthropic.Anthropic()
            )
        return self._client

    def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        budget = max_tokens or self.settings.llm_max_tokens
        payload = self._payload(messages, system, budget)
        try:
            if budget > NON_STREAMING_MAX_TOKENS:
                with self.client.messages.stream(**payload) as stream:
                    response = stream.get_final_message()
            else:
                response = self.client.messages.create(**payload)
        except Exception as exc:  # noqa: BLE001 - re-raised as a provider error below
            raise self._as_error(exc) from exc
        return self._to_response(response)

    def complete_structured(
        self,
        messages: list[LLMMessage],
        output_format: type[T],
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Return a validated pydantic model produced by the SDK's structured output path."""
        payload = self._payload(messages, system, max_tokens or self.settings.llm_max_tokens)
        try:
            parsed = self.client.messages.parse(output_format=output_format, **payload)
        except Exception as exc:  # noqa: BLE001 - re-raised as a provider error below
            raise self._as_error(exc) from exc
        value = parsed.parsed_output
        if value is None:
            raise LLMCallError(f"claude returned no structured output (stop={parsed.stop_reason})")
        return value

    def to_langchain(self) -> BaseChatModel:
        # aliases of the installed langchain-anthropic; api_key None falls back to the env var
        kwargs: dict[str, Any] = {
            "model_name": self.model,
            "api_key": self.settings.anthropic_api_key,
            "max_tokens_to_sample": self.settings.llm_max_tokens,
            "thinking": THINKING,
            "timeout": None,
            "stop": None,
        }
        return ChatAnthropic(**kwargs)

    def _payload(
        self, messages: list[LLMMessage], system: str | None, max_tokens: int
    ) -> dict[str, Any]:
        # no temperature/top_p: Opus 5 rejects sampling params
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "thinking": THINKING,
        }
        if system:
            payload["system"] = system
        return payload

    def _to_response(self, response: anthropic.types.Message) -> LLMResponse:
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=str(response.model),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    @staticmethod
    def _as_error(exc: Exception) -> LLMCallError:
        # most specific SDK error first, so the message tells the user what to fix
        if isinstance(exc, anthropic.RateLimitError):
            return LLMCallError("claude rate limit reached; retry later or lower the request rate")
        if isinstance(exc, anthropic.APIStatusError):
            return LLMCallError(f"claude api error {exc.status_code}: {exc.message}")
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMCallError(f"cannot reach the claude api: {exc}")
        return LLMCallError(f"claude call failed: {exc}")
