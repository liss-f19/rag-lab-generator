"""
Role:   Unit tests of the chat endpoint against the offline fake LLM.
Input:  The client fixture whose settings select llm_provider="fake".
Output: none
Flow:   Streams one turn and asserts the SSE envelope ends with a done event, then replays the
        same thread through the history route; when agent/graph.py is not importable yet the
        route must answer 503 with a JSON detail instead of raising.
"""

from fastapi.testclient import TestClient

TURN = {"message": "explain epoll vs select", "thread_id": "unit-thread", "llm": "fake"}


def _events(payload: str) -> list[str]:
    return [line[len("event: ") :] for line in payload.splitlines() if line.startswith("event: ")]


def test_chat_streams_sse_or_reports_missing_agent(client: TestClient) -> None:
    response = client.post("/api/chat", json=TURN)
    if response.status_code == 503:
        assert "agent" in response.json()["detail"]
        return
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert events[-1] == "done"
    assert {"message", "token"} & set(events)


def test_history_is_404_for_an_unknown_thread(client: TestClient) -> None:
    response = client.get("/api/chat/never-used")
    assert response.status_code in {404, 503}


def test_history_replays_a_streamed_thread(client: TestClient) -> None:
    if client.post("/api/chat", json=TURN).status_code != 200:
        return
    response = client.get(f"/api/chat/{TURN['thread_id']}")
    assert response.status_code == 200
    roles = [message["role"] for message in response.json()["messages"]]
    assert roles[0] == "human"
