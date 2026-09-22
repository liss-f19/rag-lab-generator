"""
Role:   Unit tests of /api/health and /api/strategies.
Input:  TestClient fixtures over an empty and a populated corpus.
Output: none
Flow:   Asserts the health probe answers even without a database and without a corpus, and that
        the strategy catalogue lists the registered names together with the Settings defaults.
"""

from fastapi.testclient import TestClient


def test_health_without_database_or_corpus(empty_client: TestClient) -> None:
    response = empty_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db_reachable"] is False
    assert body["corpus_present"] is False
    assert body["llm_provider"] == "fake"
    assert body["embedding_provider"] == "fake"


def test_health_reports_registered_strategies(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert "vector" in body["strategies"]["rag"]
    assert "fake" in body["strategies"]["embedder"]
    assert body["corpus_present"] is True


def test_strategies_lists_defaults(client: TestClient) -> None:
    body = client.get("/api/strategies").json()
    assert body["defaults"]["rag"] == "vector"
    assert "hierarchical" in body["kinds"]["chunker"]
