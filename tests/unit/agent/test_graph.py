"""
Role:   Unit tests for the compiled LangGraph agent, driven by a scripted fake chat model.
Input:  Settings with the fake provider, a scripted AIMessage sequence and a StubRAG.
Output: Assertions; no side effects.
Flow:   Runs one turn that calls generate_lab, checks the final answer, the bound tools, the
        tool message with its Sources line and the typed artifacts, then checks the system
        prompt, per-thread memory, the course filter coming from the CLI and the graceful
        answer when the knowledge base is missing.
"""

from langchain_core.messages import AIMessage, ToolMessage

from rag_lab_generator.agent.graph import build_agent, run_agent
from rag_lab_generator.agent.state import last_generated_lab, last_retrieved_context
from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.fake import FakeLLM
from rag_lab_generator.generation.llm.fake_chat import ScriptedFakeChatModel
from rag_lab_generator.models import Course

from .conftest import FailingRAG, StubRAG, default_chunks

LAB_MARKDOWN = """# L6 - FIFO similar to L5

## Description

Write a program that reads from a FIFO created with `mkfifo`.

## Stages

1. Create the pipe. *To show:* run `./prog /tmp/f`
2. Read until EOF. *To show:* echo into the pipe
"""

FINAL_ANSWER = "Here is the new task, based on sop1/l5_fifo."


def script() -> list[AIMessage]:
    call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "generate_lab",
                "args": {"topic": "FIFO", "course": "sop1", "based_on": ["sop1/l5_fifo"]},
                "id": "call-1",
            }
        ],
    )
    return [call, AIMessage(content=FINAL_ANSWER)]


def test_graph_runs_a_tool_call(settings: Settings, stub_rag: StubRAG) -> None:
    llm = FakeLLM(settings, canned=LAB_MARKDOWN, script=script())
    graph = build_agent(settings, llm=llm, rag_factory=lambda: stub_rag)
    answer = run_agent(graph, "generate a lab about FIFO similar to L5", thread_id="t1")

    assert answer == FINAL_ANSWER
    assert stub_rag.calls[0]["filters"].course == "sop1"

    chat = llm.to_langchain()
    assert isinstance(chat, ScriptedFakeChatModel)
    assert set(chat.bound_tool_names) == {"generate_lab", "explain_topic", "visualize_concept"}

    state = graph.get_state({"configurable": {"thread_id": "t1"}}).values
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert "## Stages" in tool_messages[0].content
    assert "Sources: hierarchical:sop1/l5_fifo:0" in tool_messages[0].content

    lab = last_generated_lab(state)
    assert lab is not None and lab.title == "L6 - FIFO similar to L5"
    context = last_retrieved_context(state)
    assert context is not None and context.rag == "stub"


def test_system_prompt_is_the_first_message(settings: Settings, stub_rag: StubRAG) -> None:
    llm = FakeLLM(settings, canned="ok", script=[])
    graph = build_agent(settings, llm=llm, rag_factory=lambda: stub_rag)
    run_agent(graph, "what is a FIFO?", thread_id="t2", course="sop1")
    chat = llm.to_langchain()
    assert isinstance(chat, ScriptedFakeChatModel)
    system = chat.calls[0][0]
    assert system.type == "system"
    assert "Operating Systems" in str(system.content)


def test_thread_memory_keeps_the_history(settings: Settings, stub_rag: StubRAG) -> None:
    llm = FakeLLM(settings, canned="ok")
    graph = build_agent(settings, llm=llm, rag_factory=lambda: stub_rag)
    run_agent(graph, "first question", thread_id="t3")
    run_agent(graph, "second question", thread_id="t3")
    state = graph.get_state({"configurable": {"thread_id": "t3"}}).values
    texts = [str(m.content) for m in state["messages"]]
    assert "first question" in texts and "second question" in texts
    other = graph.get_state({"configurable": {"thread_id": "t4"}}).values
    assert other == {}


def test_agent_reports_a_missing_knowledge_base(settings: Settings) -> None:
    llm = FakeLLM(settings, canned="see the tool message", script=script())
    graph = build_agent(settings, llm=llm, rag_factory=lambda: FailingRAG(settings))
    run_agent(graph, "generate a lab about FIFO", thread_id="t5")
    state = graph.get_state({"configurable": {"thread_id": "t5"}}).values
    tool_message = next(m for m in state["messages"] if isinstance(m, ToolMessage))
    assert "knowledge base is unavailable" in tool_message.content
    assert "rag-lab ingest" in tool_message.content


def test_cli_course_filter_wins_over_the_tool_default(settings: Settings) -> None:
    rag = StubRAG(settings, chunks=default_chunks(Course.SOP2))
    llm = FakeLLM(settings, canned=LAB_MARKDOWN)
    graph = build_agent(settings, llm=llm, rag_factory=lambda: rag)
    question = "generate a lab about FIFO similar to L5"
    answer = run_agent(graph, question, thread_id="t6", course="sop2")

    assert rag.calls[0]["filters"].course == "sop2"
    assert "course: sop2" in answer
    state = graph.get_state({"configurable": {"thread_id": "t6"}}).values
    lab = last_generated_lab(state)
    assert lab is not None and lab.course is Course.SOP2
