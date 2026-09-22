"""
Role:   Unit tests of the retrieval, graph, chat and eval routes without a database.
Input:  TestClient fixtures whose database url points at a closed port.
Output: none
Flow:   Asserts that every database-backed route answers 503 with a JSON detail instead of
        crashing, that an unknown strategy name is a 400, that the comparison route reports one
        error per column, and that /api/eval/runs works with no results directory.
"""

from fastapi.testclient import TestClient

from rag_lab_generator.config import Settings

QUERY = {"query": "how to list a directory", "embedder": "fake", "k": 3}


def test_retrieve_without_index_is_503(client: TestClient) -> None:
    response = client.post("/api/retrieve", json=QUERY)
    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_retrieve_with_unknown_strategy_is_400(client: TestClient) -> None:
    response = client.post("/api/retrieve", json={**QUERY, "rag": "does-not-exist"})
    assert response.status_code == 400
    assert "does-not-exist" in response.json()["detail"]


def test_retrieve_with_unknown_chunker_is_400(client: TestClient) -> None:
    response = client.post("/api/retrieve", json={**QUERY, "strategy": "not_a_chunker"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("unknown chunker strategy 'not_a_chunker'")
    assert "hierarchical" in detail


def test_compare_with_unknown_chunker_is_400(client: TestClient) -> None:
    response = client.post(
        "/api/retrieve/compare",
        json={
            **QUERY,
            "strategy": "not_a_chunker",
            "configs": [{"rag": "vector", "searcher": "lexical"}],
        },
    )
    assert response.status_code == 400
    assert "not_a_chunker" in response.json()["detail"]


def test_compare_reports_one_error_per_config(client: TestClient) -> None:
    response = client.post(
        "/api/retrieve/compare",
        json={
            **QUERY,
            "configs": [
                {"rag": "vector", "searcher": "lexical"},
                {"rag": "vector", "searcher": "dense"},
            ],
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert all(result["error"] for result in results)
    assert all(result["latency_ms"] >= 0 for result in results)


def test_graph_routes_are_503_without_database(client: TestClient) -> None:
    assert client.get("/api/graph/stats").status_code == 503
    assert client.get("/api/graph/neighbors", params={"node_id": "x"}).status_code == 503
    assert client.get("/api/graph/search", params={"q": "fork"}).status_code == 503


def test_eval_runs_without_results_dir(empty_client: TestClient) -> None:
    body = empty_client.get("/api/eval/runs").json()
    assert body["files"] == []
    assert body["db_runs"] == []
    assert body["db_reachable"] is False


def test_eval_runs_parses_csv_generically(client: TestClient, settings: Settings) -> None:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    (settings.results_dir / "matrix.csv").write_text(
        "rag,searcher,recall_at_k,mrr\nvector,dense,0.75,0.61\n", encoding="utf-8"
    )
    body = client.get("/api/eval/runs").json()
    assert body["files"][0]["columns"] == ["rag", "searcher", "recall_at_k", "mrr"]
    assert body["files"][0]["rows"][0]["recall_at_k"] == "0.75"
