"""
Role:   Unit tests for the LLM providers; no network is touched.
Input:  Settings instances and canned answers/scripts for the fake provider.
Output: Assertions; no side effects.
Flow:   Checks registration of fake and anthropic, the deterministic fake answers and its
        scripted chat model, then that AnthropicLLM constructs without a key, returns a
        ChatAnthropic with adaptive thinking and builds a payload free of sampling params.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage

from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.anthropic import THINKING, AnthropicLLM
from rag_lab_generator.generation.llm.fake import FakeLLM
from rag_lab_generator.generation.llm.fake_chat import ScriptedFakeChatModel
from rag_lab_generator.models import LLMMessage
from rag_lab_generator.registry import available, create


def test_providers_are_registered() -> None:
    assert {"fake", "anthropic"} <= set(available("llm"))


def test_fake_llm_is_constructible_through_the_registry() -> None:
    llm = create("llm", "fake", settings=Settings())
    answer = llm.complete([LLMMessage(role="user", content="explain fork")])
    assert answer.text.startswith("[fake-llm]")
    assert answer.model == "fake"


def test_fake_llm_canned_and_script() -> None:
    script = [AIMessage(content="first"), AIMessage(content="second")]
    llm = FakeLLM(Settings(), canned="canned answer", script=script)
    assert llm.complete([LLMMessage(role="user", content="x")]).text == "canned answer"
    chat = llm.to_langchain()
    assert isinstance(chat, ScriptedFakeChatModel)
    assert chat.invoke([HumanMessage(content="a")]).content == "first"
    assert chat.invoke([HumanMessage(content="b")]).content == "second"
    assert chat.invoke([HumanMessage(content="c")]).content == "canned answer"


def test_scripted_model_records_bound_tools() -> None:
    def dummy(x: str) -> str:
        """Dummy tool."""
        return x

    chat = ScriptedFakeChatModel(script=[])
    bound = chat.bind_tools([dummy])
    assert bound is chat
    assert chat.bound_tools == [dummy]


def test_anthropic_llm_constructs_without_a_key() -> None:
    llm = AnthropicLLM(Settings(anthropic_api_key=None))
    assert llm.name == "anthropic"
    assert llm.model == "claude-opus-5"
    chat = llm.to_langchain()
    assert isinstance(chat, ChatAnthropic)
    assert chat.model == "claude-opus-5"
    assert chat.thinking == THINKING
    assert chat.max_tokens == Settings().llm_max_tokens


def test_anthropic_payload_shape() -> None:
    llm = AnthropicLLM(Settings())
    payload = llm._payload([LLMMessage(role="user", content="hi")], "system prompt", 4096)
    assert payload["model"] == "claude-opus-5"
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["system"] == "system prompt"
    assert "temperature" not in payload and "top_p" not in payload
