"""
Role:   Chat endpoint: streams one agent turn as Server-Sent Events and replays a thread.
Input:  ChatRequest body (message, thread_id, course, lab_id, llm, rag); the compiled LangGraph
        agent built by rag_lab_generator.agent.graph.build_agent.
Output: SSE stream of token / message / tool_start / tool_end / context / error / done events;
        ChatHistoryResponse for a thread.
Flow:   The graph is compiled before the response starts so a missing agent still yields 503;
        astream_events maps LangGraph events onto the SSE contract, and when streaming is not
        supported the turn falls back to run_agent() in a threadpool emitting one message event.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

from rag_lab_generator.api import deps
from rag_lab_generator.api.schemas import (
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatToolCall,
)
from rag_lab_generator.config import Settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

AGENT_MODULE = "rag_lab_generator.agent.graph"
PREVIEW_CHARS = 400
MAX_SOURCES = 12
RECURSION_LIMIT = 12


def settings_of(request: Request) -> Settings:
    state: Settings = request.app.state.settings
    return state


def _settings_for(request: Request, llm: str | None, rag: str | None) -> Settings:
    """Copy the app settings with the per-request llm and rag overrides applied."""
    overrides: dict[str, str] = {}
    if llm:
        overrides["llm_provider"] = llm
    if rag:
        overrides["rag"] = rag
    settings = settings_of(request)
    return settings.model_copy(update=overrides) if overrides else settings


def _build_graph(settings: Settings) -> Any:
    build_agent = deps.module_attr(AGENT_MODULE, "build_agent")
    if build_agent is None:
        raise deps.unavailable(
            "the agent graph is not available yet: rag_lab_generator.agent.graph.build_agent"
        )
    with deps.translate("the agent graph"):
        return build_agent(settings)


# ---------------------------------------------------------------- event helpers


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


def _text_of(message: Any) -> str:
    """Flatten LangChain message content, which is either a string or a list of blocks."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return ""


def _as_context(value: Any) -> dict[str, Any] | None:
    """Recognise a RetrievedContext in a tool result, whatever shape the tool returned it in."""
    for candidate in (getattr(value, "artifact", None), value):
        if candidate is None:
            continue
        found = _context_of(candidate)
        if found is not None:
            return found
    return None


def _context_of(candidate: Any) -> dict[str, Any] | None:
    """Unwrap a ToolArtifact, a pydantic model, a mapping or a json string down to the context."""
    dumped = getattr(candidate, "model_dump", None)
    data: Any = dumped(mode="json") if callable(dumped) else candidate
    if isinstance(data, str) and data.strip().startswith("{"):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    if "chunks" in data:
        return data
    inner = data.get("context")
    return inner if isinstance(inner, dict) and "chunks" in inner else None


def _sources(context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if context is None:
        return []
    sources: list[dict[str, Any]] = []
    for scored in context.get("chunks", [])[:MAX_SOURCES]:
        chunk = scored.get("chunk", {}) if isinstance(scored, dict) else {}
        sources.append(
            {
                "chunk_id": chunk.get("id"),
                "document_id": chunk.get("document_id"),
                "lab_id": chunk.get("lab_id"),
                "section_id": chunk.get("section_id"),
                "kind": chunk.get("kind"),
                "score": scored.get("score") if isinstance(scored, dict) else None,
            }
        )
    return sources


def _preview(value: Any) -> str:
    text = _text_of(value) or str(value)
    return text[:PREVIEW_CHARS]


def _inputs(graph: Any, body: ChatRequest) -> dict[str, Any]:
    """Build the turn input with agent.state.initial_state, or with the bare message schema."""
    from langchain_core.messages import HumanMessage

    message = HumanMessage(content=body.message)
    initial_state = deps.module_attr("rag_lab_generator.agent.state", "initial_state")
    if initial_state is not None:
        state: dict[str, Any] = dict(
            initial_state(message, course=body.course, lab_id=body.lab_id, rag=body.rag)
        )
        return state
    payload: dict[str, Any] = {"messages": [message]}
    try:
        properties = graph.get_input_jsonschema().get("properties", {})
    except Exception:
        properties = {}
    for key, value in (("course", body.course), ("lab_id", body.lab_id)):
        if value is not None and key in properties:
            payload[key] = value
    return payload


# ---------------------------------------------------------------- streaming


async def _stream_events(graph: Any, body: ChatRequest) -> AsyncIterator[dict[str, str]]:
    """Map LangGraph runtime events onto the SSE contract consumed by the web client."""
    config = {"configurable": {"thread_id": body.thread_id}, "recursion_limit": RECURSION_LIMIT}
    streamed = False
    async for event in graph.astream_events(_inputs(graph, body), config=config, version="v2"):
        kind = str(event.get("event", ""))
        name = str(event.get("name", ""))
        data: dict[str, Any] = event.get("data", {}) or {}
        if kind == "on_chat_model_start":
            streamed = False
        elif kind == "on_chat_model_stream":
            text = _text_of(data.get("chunk"))
            if text:
                streamed = True
                yield _sse("token", {"text": text})
        elif kind == "on_chat_model_end":
            text = _text_of(data.get("output"))
            if text and not streamed:
                yield _sse("message", {"text": text})
        elif kind == "on_tool_start":
            yield _sse("tool_start", {"name": name, "args": data.get("input", {})})
        elif kind == "on_tool_end":
            output = data.get("output")
            context = _as_context(output)
            yield _sse(
                "tool_end",
                {
                    "name": name,
                    "output_preview": _preview(output),
                    "sources": _sources(context),
                },
            )
            if context is not None:
                yield _sse("context", {"name": name, "context": context})


async def _fallback_events(
    graph: Any, settings: Settings, body: ChatRequest
) -> AsyncIterator[dict[str, str]]:
    """Single-shot turn used when the graph cannot stream: run_agent() in a threadpool."""
    run_agent = deps.module_attr(AGENT_MODULE, "run_agent")
    if run_agent is None:
        yield _sse("error", {"message": "the agent graph exposes neither streaming nor run_agent"})
        return
    try:
        answer = await run_in_threadpool(
            run_agent, graph, body.message, body.thread_id, body.course
        )
    except Exception as exc:
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
        return
    yield _sse("message", {"text": str(answer)})


async def _events(
    graph: Any, settings: Settings, body: ChatRequest
) -> AsyncIterator[dict[str, str]]:
    emitted = False
    try:
        async for event in _stream_events(graph, body):
            emitted = True
            yield event
    except Exception as exc:
        if emitted:
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
        else:
            async for event in _fallback_events(graph, settings, body):
                yield event
    yield _sse("done", {"thread_id": body.thread_id})


def _cache(request: Request) -> dict[tuple[str, str], Any]:
    """Compiled graphs live on app.state so the in-memory checkpointer keeps thread history."""
    cached: dict[tuple[str, str], Any] | None = getattr(request.app.state, "agent_graphs", None)
    if cached is None:
        cached = {}
        request.app.state.agent_graphs = cached
    return cached


async def _graph_for(request: Request, settings: Settings) -> Any:
    cache = _cache(request)
    key = (settings.llm_provider, settings.rag)
    if key not in cache:
        cache[key] = await run_in_threadpool(_build_graph, settings)
    return cache[key]


def _messages_of(graph: Any, thread_id: str) -> list[Any]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = graph.get_state(config)
    except Exception:
        return []
    values = getattr(state, "values", {}) or {}
    return list(values.get("messages", []))


@router.post("")
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    """Stream one agent turn; the graph is compiled first so failures stay plain HTTP errors."""
    settings = _settings_for(request, body.llm, body.rag)
    graph = await _graph_for(request, settings)
    return EventSourceResponse(_events(graph, settings, body))


@router.get("/{thread_id}", response_model=ChatHistoryResponse)
async def history(thread_id: str, request: Request) -> ChatHistoryResponse:
    """Replay a thread from the checkpointer; 404 when no compiled graph holds that thread."""
    graphs = list(_cache(request).values())
    if not graphs:
        graphs = [await _graph_for(request, settings_of(request))]
    for graph in graphs:
        messages = await run_in_threadpool(_messages_of, graph, thread_id)
        if messages:
            return ChatHistoryResponse(
                thread_id=thread_id, messages=[_message(m) for m in messages]
            )
    raise HTTPException(status_code=404, detail=f"no history for thread {thread_id!r}")


def _message(message: Any) -> ChatMessage:
    calls = getattr(message, "tool_calls", None) or []
    return ChatMessage(
        role=str(getattr(message, "type", "assistant")),
        content=_text_of(message),
        tool_calls=[
            ChatToolCall(name=str(call.get("name", "")), args=dict(call.get("args", {})))
            for call in calls
            if isinstance(call, dict)
        ],
    )
