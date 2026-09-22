"""
Role:   Independent QA contract tests of the FastAPI layer consumed by the web client.
Input:  The real application from api.app.create_app driven through fastapi.testclient;
        the corpus under data/raw and the shared Postgres when they are present.
Output: Assertions on status codes, response shapes, path-traversal refusal, error mapping,
        the chat SSE event contract and the CORS headers the Vite dev server needs.
Flow:   A module-scoped client runs against Settings forced to the fake embedder and fake llm;
        helpers probe the corpus and the database once and skip the tests that need them, so the
        suite stays green on a machine without data while still failing on real contract breaks.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rag_lab_generator.api.app import create_app
from rag_lab_generator.api.deps import db_reachable
from rag_lab_generator.config import Settings
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

DEV_ORIGIN = "http://localhost:5173"
LAB_COURSE = "sop1"
LAB_SLUG = "l1_filesystem"
EXPECTED_COURSES = 2
EXPECTED_LABS = 12

# Paths a client must never be able to read through the attachment route.
TRAVERSAL_PATHS = (
    "../../../../etc/passwd",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "/etc/passwd",
    "src/../../../../etc/passwd",
    "src/../../sop2/netcat/lab.xml",
    "....//....//etc/passwd",
)


@pytest.fixture(scope="module")
def settings() -> Settings:
    """The real settings with the deterministic providers forced on."""
    return Settings(embedding_provider="fake", llm_provider="fake")


@pytest.fixture(scope="module")
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def has_corpus(settings: Settings) -> bool:
    return settings.raw_dir.is_dir() and any(settings.raw_dir.iterdir())


@pytest.fixture(scope="module")
def has_db(settings: Settings) -> bool:
    """Reachable *and* indexed: hierarchical chunks, fake vectors and graph nodes are present."""
    if not db_reachable(settings):
        return False
    with PostgresStore(settings).connection() as conn:
        row = conn.execute(
            "SELECT (SELECT count(*) FROM chunks WHERE strategy = 'hierarchical') AS chunks,"
            " (SELECT count(*) FROM embeddings WHERE embedder = 'fake') AS vectors,"
            " (SELECT count(*) FROM nodes) AS nodes"
        ).fetchone()
    return bool(row and row["chunks"] and row["vectors"] and row["nodes"])


def need_corpus(has_corpus: bool) -> None:
    if not has_corpus:
        pytest.skip("data/raw is empty: ingest the corpus first")


def need_db(has_db: bool) -> None:
    if not has_db:
        pytest.skip("Postgres unreachable or not indexed (rag-lab chunk / index / graph-build)")


def retrieve(client: TestClient, **body: Any) -> Any:
    return client.post("/api/retrieve", json=body)


# ---------------------------------------------------------------- health


def test_health_returns_the_full_configuration_shape(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    required = {
        "version",
        "llm_provider",
        "llm_model",
        "embedding_provider",
        "rag",
        "searcher",
        "chunker",
        "retrieval_k",
        "data_dir",
        "db_reachable",
        "corpus_present",
        "agent_available",
        "graph_available",
        "strategies",
    }
    assert required <= set(body)
    assert body["llm_provider"] == "fake"
    assert body["embedding_provider"] == "fake"
    assert isinstance(body["retrieval_k"], int)
    for flag in ("db_reachable", "corpus_present", "agent_available", "graph_available"):
        assert isinstance(body[flag], bool)


def test_health_strategies_list_every_registry_kind(client: TestClient) -> None:
    strategies = client.get("/api/health").json()["strategies"]
    for kind in ("chunker", "embedder", "searcher", "rag", "llm"):
        assert kind in strategies, f"health forgot the {kind} kind"
        assert isinstance(strategies[kind], list)
    assert "fake" in strategies["embedder"]
    assert "hierarchical" in strategies["chunker"]


# ---------------------------------------------------------------- corpus


def test_courses_expose_two_courses_and_twelve_labs(client: TestClient, has_corpus: bool) -> None:
    need_corpus(has_corpus)
    body = client.get("/api/courses").json()
    assert body["corpus_present"] is True
    assert len(body["courses"]) == EXPECTED_COURSES
    assert {course["course"] for course in body["courses"]} == {"sop1", "sop2"}
    labs = [lab for course in body["courses"] for lab in course["labs"]]
    assert len(labs) == EXPECTED_LABS
    for course in body["courses"]:
        assert course["n_labs"] == len(course["labs"])


def test_every_lab_summary_carries_the_counters_the_ui_renders(
    client: TestClient, has_corpus: bool
) -> None:
    need_corpus(has_corpus)
    body = client.get("/api/courses").json()
    for course in body["courses"]:
        for lab in course["labs"]:
            assert set(lab) >= {"id", "course", "slug", "title", "number", "n_tasks", "n_files"}
            assert lab["title"], f"{lab['id']} has an empty title"
            assert lab["n_files"] > 0, f"{lab['id']} lists no attachment"


def test_lab_detail_returns_sections_tasks_and_summary(
    client: TestClient, has_corpus: bool
) -> None:
    need_corpus(has_corpus)
    response = client.get(f"/api/labs/{LAB_COURSE}/{LAB_SLUG}")
    assert response.status_code == 200
    body = response.json()
    lab = body["lab"]
    assert lab["course"] == LAB_COURSE
    assert lab["slug"] == LAB_SLUG
    assert len(lab["sections"]) > 0
    assert len(lab["tasks"]) > 0
    assert body["summary"], "summary.md was not picked up"
    assert body["files"], "the attachment listing is empty"
    first = lab["sections"][0]
    assert set(first) >= {"id", "title", "level", "order", "text"}
    task = lab["tasks"][0]
    assert set(task) >= {"id", "title", "statement", "stages"}


def test_unknown_lab_is_a_404(client: TestClient) -> None:
    assert client.get("/api/labs/sop1/does_not_exist").status_code == 404
    assert client.get("/api/labs/nope/nope").status_code == 404


def test_file_route_serves_a_c_file_inline(client: TestClient, has_corpus: bool) -> None:
    need_corpus(has_corpus)
    listing = client.get(f"/api/labs/{LAB_COURSE}/{LAB_SLUG}").json()["files"]
    c_files = [entry["path"] for entry in listing if entry["path"].endswith(".c")]
    assert c_files, "the lab lists no .c attachment"
    response = client.get(f"/api/labs/{LAB_COURSE}/{LAB_SLUG}/files/{c_files[0]}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(("text/", "application/octet-stream"))
    assert "inline" in response.headers.get("content-disposition", "")
    assert response.text.strip(), "the served file is empty"


@pytest.mark.parametrize("path", TRAVERSAL_PATHS)
def test_file_route_refuses_to_escape_the_lab_folder(
    client: TestClient, has_corpus: bool, path: str
) -> None:
    need_corpus(has_corpus)
    response = client.get(f"/api/labs/{LAB_COURSE}/{LAB_SLUG}/files/{path}", follow_redirects=False)
    assert response.status_code in (400, 404), f"{path} was not refused"
    assert "root:x:" not in response.text


def test_file_route_refuses_a_traversal_in_the_slug(client: TestClient) -> None:
    response = client.get("/api/labs/sop1/..%2F..%2Fetc/files/passwd", follow_redirects=False)
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------- strategies


def test_strategies_lists_the_registry_and_the_defaults(client: TestClient) -> None:
    body = client.get("/api/strategies").json()
    kinds, defaults = body["kinds"], body["defaults"]
    assert {"chunker", "embedder", "searcher", "rag", "llm"} <= set(kinds)
    assert {"vector", "graph"} <= set(kinds["rag"])
    assert {"lexical", "dense", "hybrid_rrf", "graph_walk"} <= set(kinds["searcher"])
    assert {"rag", "searcher", "chunker", "embedder", "llm"} <= set(defaults)
    # every default must be a name the registry actually knows, or the UI preselects a broken value
    for key, kind in (("rag", "rag"), ("searcher", "searcher"), ("chunker", "chunker")):
        assert defaults[key] in kinds[kind], f"default {key}={defaults[key]!r} is not registered"


# ---------------------------------------------------------------- retrieval


def test_retrieve_returns_chunks_for_readdir(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    response = retrieve(
        client,
        query="readdir",
        rag="vector",
        searcher="lexical",
        strategy="hierarchical",
        embedder="fake",
        k=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["config"] == {
        "rag": "vector",
        "searcher": "lexical",
        "strategy": "hierarchical",
        "embedder": "fake",
        "k": 5,
    }
    assert body["latency_ms"] > 0
    chunks = body["context"]["chunks"]
    assert chunks, "no chunk came back: run `rag-lab chunk` and `rag-lab index` first"
    for scored in chunks:
        assert set(scored) >= {"chunk", "score", "source"}
        assert set(scored["chunk"]) >= {"id", "document_id", "course", "kind", "text"}
        assert scored["chunk"]["text"].strip()
    assert any(scored["chunk"]["lab_id"] == "sop1/l1" for scored in chunks), (
        "a readdir query did not surface a single sop1/l1 chunk"
    )


def test_retrieve_never_repeats_a_chunk_id(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    chunks = retrieve(client, query="readdir", searcher="hybrid_rrf", embedder="fake", k=8).json()[
        "context"
    ]["chunks"]
    ids = [scored["chunk"]["id"] for scored in chunks]
    assert len(ids) == len(set(ids)), "the same chunk was returned twice"


def test_retrieve_scores_are_ordered_best_first(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    chunks = retrieve(client, query="readdir", searcher="lexical", embedder="fake", k=8).json()[
        "context"
    ]["chunks"]
    scores = [scored["score"] for scored in chunks]
    assert scores == sorted(scores, reverse=True), f"scores are not descending: {scores}"


def test_graph_rag_reports_the_path_that_found_each_chunk(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    response = retrieve(
        client, query="readdir", rag="graph", searcher="graph_walk", embedder="fake", k=5
    )
    assert response.status_code == 200
    trace = response.json()["context"]["trace"]
    assert "paths" in trace, "the graph rag trace carries no path the UI could display"
    assert "seed_nodes" in trace


def test_compare_runs_every_configuration_and_keeps_per_column_results(
    client: TestClient, has_db: bool
) -> None:
    need_db(has_db)
    response = client.post(
        "/api/retrieve/compare",
        json={
            "query": "readdir",
            "k": 5,
            "strategy": "hierarchical",
            "embedder": "fake",
            "configs": [
                {"rag": "vector", "searcher": "hybrid_rrf"},
                {"rag": "graph", "searcher": "graph_walk"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "readdir"
    assert len(body["results"]) == 2
    for result in body["results"]:
        assert result["error"] is None, result["error"]
        assert result["context"] is not None
        assert result["context"]["chunks"], f"{result['config']} returned nothing"
        assert result["latency_ms"] > 0
    assert [r["config"]["rag"] for r in body["results"]] == ["vector", "graph"]


def test_compare_isolates_a_failing_column_instead_of_failing_the_request(
    client: TestClient, has_db: bool
) -> None:
    need_db(has_db)
    response = client.post(
        "/api/retrieve/compare",
        json={
            "query": "readdir",
            "k": 5,
            "embedder": "fake",
            "configs": [
                {"rag": "vector", "searcher": "lexical"},
                {"rag": "nope", "searcher": "lexical"},
            ],
        },
    )
    assert response.status_code == 200
    good, bad = response.json()["results"]
    assert good["error"] is None
    assert bad["error"] is not None
    assert bad["context"] is None


# ---------------------------------------------------------------- error mapping


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"query": ""},
        {"query": "x", "k": 0},
        {"query": "x", "k": 999},
        {"query": 123},
    ],
)
def test_invalid_retrieve_bodies_are_422(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/api/retrieve", json=body).status_code == 422


@pytest.mark.parametrize(
    "body", [{}, {"message": "hi"}, {"message": "", "thread_id": "t"}, {"thread_id": "t"}]
)
def test_invalid_chat_bodies_are_422(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/api/chat", json=body).status_code == 422


@pytest.mark.parametrize("field", ["rag", "searcher", "embedder"])
def test_unknown_strategy_names_are_a_helpful_4xx(
    client: TestClient, has_db: bool, field: str
) -> None:
    need_db(has_db)
    response = retrieve(client, query="readdir", **{field: "definitely_not_registered"})
    assert 400 <= response.status_code < 500, f"unknown {field} produced {response.status_code}"
    detail = response.json()["detail"]
    assert "definitely_not_registered" in detail
    assert "available" in detail, f"the {field} error does not list the valid names: {detail}"
    assert not detail.startswith('"'), (
        f"the detail is a repr of a KeyError, not a sentence: {detail!r}"
    )


def test_unknown_chunking_strategy_is_reported_not_silently_empty(
    client: TestClient, has_db: bool
) -> None:
    """A chunker name that was never registered must not look like 'your query found nothing'."""
    need_db(has_db)
    response = retrieve(client, query="readdir", strategy="definitely_not_registered")
    if response.status_code == 200:
        chunks = response.json()["context"]["chunks"]
        assert chunks, (
            "an unregistered chunking strategy returned 200 with zero chunks; the UI cannot "
            "tell a bad strategy name from an empty result set"
        )
    else:
        assert 400 <= response.status_code < 500
        assert "definitely_not_registered" in response.json()["detail"]


# ---------------------------------------------------------------- graph


def test_graph_search_finds_epoll(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    response = client.get("/api/graph/search", params={"q": "epoll", "limit": 30})
    assert response.status_code == 200
    body = response.json()
    assert body["nodes"], "no graph node matches epoll: run `rag-lab graph-build`"
    for node in body["nodes"]:
        assert set(node) >= {"id", "kind", "label", "degree", "chunk_ids"}
        assert "epoll" in node["label"].lower()
    node_ids = {node["id"] for node in body["nodes"]}
    for edge in body["edges"]:
        assert edge["src"] in node_ids and edge["dst"] in node_ids


def test_graph_neighbors_expands_a_node(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    matches = client.get("/api/graph/search", params={"q": "epoll"}).json()["nodes"]
    if not matches:
        pytest.skip("the graph holds no epoll node")
    node_id = matches[0]["id"]
    body = client.get("/api/graph/neighbors", params={"node_id": node_id, "hops": 1}).json()
    assert body["center"] == node_id
    assert body["hops"] == 1
    assert any(node["hops"] == 0 for node in body["nodes"])


def test_graph_chunks_of_a_node_carry_text(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    matches = client.get("/api/graph/search", params={"q": "epoll"}).json()["nodes"]
    with_chunks = [node for node in matches if node["chunk_ids"]]
    if not with_chunks:
        pytest.skip("no epoll node carries chunks")
    body = client.get("/api/graph/chunks", params={"node_id": with_chunks[0]["id"]}).json()
    assert body["chunks"], "the details panel of the graph page would stay empty"
    for chunk in body["chunks"]:
        assert set(chunk) >= {"id", "document_id", "kind", "text"}


def test_graph_rejects_a_missing_node_and_a_too_large_hop_count(client: TestClient) -> None:
    assert client.get("/api/graph/search").status_code == 422
    assert client.get("/api/graph/neighbors", params={"node_id": "x", "hops": 9}).status_code == 422


# ---------------------------------------------------------------- chat


def read_sse(client: TestClient, body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Collect (event, payload) pairs from one streamed chat turn."""
    events: list[tuple[str, dict[str, Any]]] = []
    with client.stream("POST", "/api/chat", json=body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        name = ""
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                raw = line.split(":", 1)[1].strip()
                try:
                    events.append((name, json.loads(raw)))
                except json.JSONDecodeError:
                    events.append((name, {"raw": raw}))
    return events


def test_chat_stream_ends_with_done_and_carries_an_answer(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    events = read_sse(client, {"message": "explain zombie process", "thread_id": "qa-contract-1"})
    names = [name for name, _ in events]
    assert names, "the chat stream produced no event at all"
    assert names[-1] == "done", f"the stream does not end with done: {names}"
    assert names.count("done") == 1
    assert "error" not in names, [payload for name, payload in events if name == "error"]
    answer = "".join(
        payload.get("text", "") for name, payload in events if name in ("token", "message")
    )
    assert answer.strip(), "no token or message event carried any text"


def test_chat_emits_paired_tool_events_with_sources(client: TestClient, has_db: bool) -> None:
    need_db(has_db)
    events = read_sse(client, {"message": "explain zombie process", "thread_id": "qa-contract-2"})
    starts = [payload for name, payload in events if name == "tool_start"]
    ends = [payload for name, payload in events if name == "tool_end"]
    assert starts, "the agent answered without calling a single tool"
    assert len(starts) == len(ends), "a tool_start has no matching tool_end"
    for payload in starts:
        assert payload["name"]
        assert isinstance(payload["args"], dict)
    for payload in ends:
        assert payload["name"]
        assert "output_preview" in payload
        assert isinstance(payload["sources"], list)
    contexts = [payload for name, payload in events if name == "context"]
    assert contexts, "no context event: the UI cannot show which chunks grounded the answer"
    assert contexts[0]["context"]["chunks"]


def test_chat_history_replays_a_thread_and_404s_on_an_unknown_one(
    client: TestClient, has_db: bool
) -> None:
    need_db(has_db)
    thread = "qa-contract-history"
    read_sse(client, {"message": "what is a pipe", "thread_id": thread})
    body = client.get(f"/api/chat/{thread}").json()
    assert body["thread_id"] == thread
    assert body["messages"], "the replayed thread is empty"
    assert body["messages"][0]["role"] == "human"
    assert client.get("/api/chat/never-used-thread-qa").status_code == 404


# ---------------------------------------------------------------- eval


def test_eval_runs_answers_even_without_results(client: TestClient) -> None:
    response = client.get("/api/eval/runs")
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"results_dir", "db_reachable", "files", "db_runs"}
    assert isinstance(body["files"], list)
    assert isinstance(body["db_runs"], list)
    for run in body["db_runs"]:
        assert set(run) >= {"id", "created_at", "config", "metrics"}
        assert isinstance(run["config"], dict)
        assert isinstance(run["metrics"], dict)


# ---------------------------------------------------------------- CORS


def test_cors_allows_the_vite_dev_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": DEV_ORIGIN})
    assert response.headers.get("access-control-allow-origin") == DEV_ORIGIN


def test_cors_preflight_allows_a_json_post(client: TestClient) -> None:
    response = client.options(
        "/api/retrieve",
        headers={
            "Origin": DEV_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == DEV_ORIGIN
    assert "POST" in response.headers.get("access-control-allow-methods", "")
