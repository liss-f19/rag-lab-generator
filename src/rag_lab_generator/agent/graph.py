"""
Role:   Builds and runs the LangGraph ReAct agent that answers student questions.
Input:  Settings, an optional LLM (registry default otherwise) and an optional RagFactory.
Output: A compiled LangGraph with a MemorySaver checkpointer; run_agent() returns the answer.
Flow:   build_agent() resolves the LLM through the registry, builds the three tools around one
        retrieval stack, binds them to the LangChain chat model and compiles a prebuilt ReAct
        graph with the system prompt and per-thread memory; run_agent() invokes one turn with a
        thread id and returns the text of the final assistant message.
"""

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from rag_lab_generator.agent.rag_factory import RagFactory, make_rag_factory
from rag_lab_generator.agent.state import AgentState, initial_state, last_answer
from rag_lab_generator.agent.tools import explain_topic, generate_lab, visualize_concept
from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.generation.prompts import load_prompt
from rag_lab_generator.registry import create

AgentGraph = CompiledStateGraph[AgentState, Any, Any, Any]

RECURSION_LIMIT = 12


def build_agent(
    settings: Settings,
    llm: LLM | None = None,
    rag_factory: RagFactory | None = None,
) -> AgentGraph:
    """Compile the agent: system prompt, three grounded tools, per-thread memory."""
    model = llm or create("llm", settings.llm_provider, settings=settings)
    factory = rag_factory or make_rag_factory(settings, settings.rag)
    tools = [
        generate_lab.make_tool(factory, model, settings),
        explain_topic.make_tool(factory, model, settings),
        visualize_concept.make_tool(factory, model, settings),
    ]
    graph: AgentGraph = create_react_agent(
        model.to_langchain(),
        tools,
        prompt=load_prompt("system_agent"),
        state_schema=AgentState,
        checkpointer=MemorySaver(),
        name="sop-assistant",
    )
    return graph


def run_agent(
    graph: AgentGraph,
    message: str,
    thread_id: str = "default",
    course: str | None = None,
    lab_id: str | None = None,
) -> str:
    """Run one turn on the given conversation thread and return the assistant answer."""
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    state = graph.invoke(
        initial_state(HumanMessage(content=message), course=course, lab_id=lab_id),
        config=config,
    )
    return last_answer(dict(state))
