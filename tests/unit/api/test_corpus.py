"""
Role:   Unit tests of the corpus routes over a temporary data/raw tree.
Input:  The client fixture built on the lab.xml fixture.
Output: none
Flow:   Checks the course listing, the parsed LabDocument, the attachment listing, the file
        route and that a path escaping the lab folder is refused with 404.
"""

from fastapi.testclient import TestClient


def test_courses_lists_the_fixture_lab(client: TestClient) -> None:
    body = client.get("/api/courses").json()
    assert body["corpus_present"] is True
    course = body["courses"][0]
    assert course["course"] == "sop1"
    lab = course["labs"][0]
    assert lab["slug"] == "l1_filesystem"
    assert lab["title"] == "Filesystem API"
    assert lab["number"] == "1"
    assert lab["n_tasks"] == 1
    assert lab["n_sections"] == 2
    assert lab["has_summary"] is True


def test_courses_without_corpus(empty_client: TestClient) -> None:
    body = empty_client.get("/api/courses").json()
    assert body["courses"] == []
    assert body["corpus_present"] is False


def test_lab_detail_parses_lab_xml(client: TestClient) -> None:
    body = client.get("/api/labs/sop1/l1_filesystem").json()
    lab = body["lab"]
    assert lab["id"] == "sop1/l1_filesystem"
    assert lab["topics"] == ["open", "readdir", "stat"]
    assert lab["sections"][0]["id"] == "browsing-a-directory"
    assert lab["sections"][0]["code_refs"] == ["src/prog1.c"]
    assert lab["sections"][1]["parent_id"] == "browsing-a-directory"
    task = lab["tasks"][0]
    assert task["id"] == "example1"
    assert [stage["n"] for stage in task["stages"]] == [1, 2]
    assert task["notes"] == "Remember to closedir."
    assert lab["references"][0]["title"] == "readdir(3)"
    assert body["summary"].startswith("# Filesystem API")
    assert body["manifest"]["slug"] == "l1_filesystem"
    assert [entry["path"] for entry in body["files"]] == ["src/prog1.c"]


def test_missing_lab_is_404(client: TestClient) -> None:
    assert client.get("/api/labs/sop1/nope").status_code == 404


def test_file_route_serves_source(client: TestClient) -> None:
    response = client.get("/api/labs/sop1/l1_filesystem/files/src/prog1.c")
    assert response.status_code == 200
    assert "int main" in response.text


def test_file_route_blocks_traversal(client: TestClient) -> None:
    for path in ("../../../etc/passwd", "src/../../lab.xml", "..%2f..%2fsummary.md"):
        assert client.get(f"/api/labs/sop1/l1_filesystem/files/{path}").status_code == 404
    assert client.get("/api/labs/../sop1/l1_filesystem").status_code == 404
