"""
Role:   Unit tests for the three agent tools; no network and no database.
Input:  A StubRAG or FailingRAG, the fake LLM with canned answers and tool call payloads.
Output: Assertions; no side effects.
Flow:   Invokes each tool the way the tool node does, checks the rendered answer, the Sources
        line, the ToolArtifact it carries, how the course is resolved from the argument, the
        state or the reference labs, and the message the tools return when retrieval fails.
"""

from typing import Any

from langchain_core.messages import ToolMessage

from rag_lab_generator.agent.state import ToolArtifact
from rag_lab_generator.agent.tools import explain_topic, generate_lab, visualize_concept
from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.fake import FakeLLM
from rag_lab_generator.models import Course, GeneratedLab

from .conftest import FailingRAG, StubRAG, default_chunks

LAB_MARKDOWN = """# L7 - FIFO chat

## Description

Write a program using `mkfifo` that reads messages from a named pipe.

## Stages

1. Create the FIFO. *To show:* run `./prog /tmp/chat`
2. Read until EOF. *To show:* write with echo
"""


def invoke(tool: Any, args: dict[str, Any], state: dict[str, Any] | None = None) -> ToolMessage:
    call = {
        "name": tool.name,
        "args": args,
        "id": "call-1",
        "type": "tool_call",
    }
    message = tool.invoke({**call, "args": {**args, "state": state or {"messages": []}}})
    assert isinstance(message, ToolMessage)
    return message


def test_generate_lab_parses_markdown_and_lists_sources(
    settings: Settings, stub_rag: StubRAG
) -> None:
    llm = FakeLLM(settings, canned=LAB_MARKDOWN)
    tool = generate_lab.make_tool(lambda: stub_rag, llm, settings)
    message = invoke(tool, {"topic": "FIFO chat", "course": "sop1", "based_on": ["sop1/l5_fifo"]})

    assert isinstance(message.content, str)
    assert "# L7 - FIFO chat" in message.content
    assert "## Stages" in message.content
    assert "Sources: hierarchical:sop1/l5_fifo:0, hierarchical:sop1/l5_fifo:1" in message.content

    artifact = message.artifact
    assert isinstance(artifact, ToolArtifact)
    lab = artifact.lab
    assert isinstance(lab, GeneratedLab)
    assert lab.title == "L7 - FIFO chat"
    assert lab.based_on == ["sop1/l5_fifo"]
    assert len(lab.stages) == 2
    assert stub_rag.calls[0]["filters"].course == "sop1"
    assert stub_rag.calls[0]["k"] == settings.retrieval_k


def test_generate_lab_accepts_json_answers(settings: Settings, stub_rag: StubRAG) -> None:
    canned = (
        '{"title": "L8 - pipes", "topics": ["pipe"], "description": "Write a program.",'
        ' "stages": ["stage one. To show: run it"], "hints": [], "difficulty": "hard"}'
    )
    tool = generate_lab.make_tool(lambda: stub_rag, FakeLLM(settings, canned=canned), settings)
    message = invoke(tool, {"topic": "pipes", "course": "sop2", "difficulty": "hard"})
    lab = message.artifact.lab
    assert lab.title == "L8 - pipes"
    assert lab.difficulty == "hard"
    assert lab.course.value == "sop2"


def test_state_filters_reach_the_rag(settings: Settings, stub_rag: StubRAG) -> None:
    tool = explain_topic.make_tool(lambda: stub_rag, FakeLLM(settings), settings)
    state = {"messages": [], "course": "sop2", "lab_id": "sop2/l3", "retrieval_k": 1}
    invoke(tool, {"topic": "epoll"}, state=state)
    call = stub_rag.calls[0]
    assert call["filters"].lab_id == "sop2/l3"
    assert call["filters"].strategy == "hierarchical"
    assert call["k"] == 1


def test_explain_topic_appends_sources(settings: Settings, stub_rag: StubRAG) -> None:
    llm = FakeLLM(settings, canned="signals are")
    tool = explain_topic.make_tool(lambda: stub_rag, llm, settings)
    message = invoke(tool, {"topic": "signals", "course": "sop1", "depth": "short"})
    assert message.content.startswith("signals are")
    assert message.content.strip().endswith("hierarchical:sop1/l5_fifo:1")
    assert message.artifact.context is not None


def test_visualize_concept_returns_a_mermaid_block(settings: Settings, stub_rag: StubRAG) -> None:
    diagram = "```mermaid\nflowchart TD\n    A[fork] --> B[exec]\n```\n\nThe parent waits."
    llm = FakeLLM(settings, canned=diagram)
    tool = visualize_concept.make_tool(lambda: stub_rag, llm, settings)
    message = invoke(tool, {"concept": "fork/exec/wait", "diagram_type": "flowchart"})
    assert "```mermaid" in message.content
    assert "flowchart TD" in message.content
    assert "Sources:" in message.content


def test_visualize_concept_fences_plain_text(settings: Settings, stub_rag: StubRAG) -> None:
    llm = FakeLLM(settings, canned="no fence")
    tool = visualize_concept.make_tool(lambda: stub_rag, llm, settings)
    message = invoke(tool, {"concept": "pipes", "diagram_type": "sequenceDiagram"})
    assert message.content.startswith("```mermaid\nsequenceDiagram")
    assert "no fence" in message.content


def test_tools_report_an_unavailable_knowledge_base(settings: Settings) -> None:
    failing = FailingRAG(settings)
    tool = generate_lab.make_tool(lambda: failing, FakeLLM(settings), settings)
    message = invoke(tool, {"topic": "FIFO"})
    assert "knowledge base is unavailable" in message.content
    assert "rag-lab ingest" in message.content
    assert message.artifact.lab is None


def test_course_is_inferred_from_the_reference_labs(settings: Settings) -> None:
    rag = StubRAG(settings, chunks=default_chunks(Course.SOP2))
    tool = generate_lab.make_tool(lambda: rag, FakeLLM(settings, canned=LAB_MARKDOWN), settings)
    message = invoke(tool, {"topic": "threads", "based_on": ["sop2/l2_threads"]})
    assert rag.calls[0]["filters"].course == "sop2"
    assert message.artifact.lab.course is Course.SOP2


def test_course_falls_back_to_the_retrieved_material(settings: Settings) -> None:
    rag = StubRAG(settings, chunks=default_chunks(Course.SOP2))
    tool = generate_lab.make_tool(lambda: rag, FakeLLM(settings, canned=LAB_MARKDOWN), settings)
    message = invoke(tool, {"topic": "sockets"})
    assert rag.calls[0]["filters"].course is None
    assert message.artifact.lab.course is Course.SOP2


def test_state_course_wins_when_the_model_omits_it(settings: Settings) -> None:
    rag = StubRAG(settings, chunks=default_chunks(Course.SOP2))
    state = {"messages": [], "course": "sop2"}
    for factory in (generate_lab, explain_topic, visualize_concept):
        rag.calls.clear()
        tool = factory.make_tool(lambda: rag, FakeLLM(settings, canned="x"), settings)
        args = {"concept": "pipes"} if factory is visualize_concept else {"topic": "pipes"}
        invoke(tool, args, state=state)
        assert rag.calls[0]["filters"].course == "sop2"
