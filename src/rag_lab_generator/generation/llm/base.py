"""
Role:   Abstract base for chat LLM providers.
Input:  Settings (model, max tokens, api key); messages and system prompt at call time.
Output: LLMResponse with text and token usage.
Flow:   Subclasses implement complete(); to_langchain() exposes the provider as a LangChain
        chat model so the LangGraph agent can bind tools to it.
"""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel

from rag_lab_generator.config import Settings
from rag_lab_generator.models import LLMMessage, LLMResponse


class LLM(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.llm_model

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    def to_langchain(self) -> BaseChatModel: ...
