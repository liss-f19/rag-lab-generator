"""HTTP contract of /api/v1: status codes, error envelope, roles, and job flow."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rag_lab_generator.api.app import create_app
from rag_lab_generator.domain.models import UserRole
from tests.conftest import AppEnvironment, build_environment
from tests.fakes import make_pdf

API = "/api/v1"
MUTEX = b"# Synchronization\n## Mutex\nA mutex protects a critical section.\n"
DATASET = Path(__file__).resolve().parents[2] / "dataset"


def _metadata(**overrides: object) -> str:
    values: dict[str, object] = {
        "course_id": "operating-systems",
        "knowledge_base": "primary",
        "document_type": "tutorial",
        "topic": "process_synchronization",
        "version": "2026",
        "learning_outcomes": ["LO-3"],
        "authority_level": "course",
    }
    values.update(overrides)
    return json.dumps(values)


def _upload(
    client: TestClient,
    headers: dict[str, str],
    data: bytes = MUTEX,
    name: str = "l4.md",
    **meta: object,
):  # type: ignore[no-untyped-def]
    return client.post(
        f"{API}/documents",
        headers=headers,
        files={"file": (name, data, "application/octet-stream")},
        data={"metadata": _metadata(**meta)},
    )


def _assert_error(response, status: int, code: str) -> dict:  # type: ignore[no-untyped-def]
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


def test_health_reports_database_and_queue(client: TestClient) -> None:
    response = client.get(f"{API}/health")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "queue": "ok"}


def test_health_is_degraded_when_the_queue_is_down(tmp_path: Path) -> None:
    env = build_environment(tmp_path, inline=False)
    env.queue.fail = True  # type: ignore[union-attr]
    with TestClient(create_app(env.container)) as client:
        response = client.get(f"{API}/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_upload_is_accepted_and_ingested(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    response = _upload(client, instructor_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status_url"] == f"{API}/jobs/{body['job_id']}"

    job = client.get(body["status_url"], headers=instructor_headers).json()
    assert job["status"] == "succeeded"
    assert job["job_type"] == "document_ingestion"
    assert job["result"]["chunk_count"] == 1
    assert job["error"] is None

    document = client.get(
        f"{API}/documents/{body['document_id']}", headers=instructor_headers
    ).json()
    assert document["ingestion_status"] == "indexed"
    assert document["chunk_count"] == 1
    assert document["metadata"]["learning_outcomes"] == ["LO-3"]

    logs = client.get(f"{body['status_url']}/logs", headers=instructor_headers).json()
    assert [log["event_type"] for log in logs] == [
        "job.queued",
        "job.started",
        "job.succeeded",
    ]


def test_all_supported_formats_are_ingested(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    files = {
        "notes.md": MUTEX,
        "notes.txt": b"Plain text about semaphores.",
        "page.html": b"<h1>Pipes</h1><p>Pipes connect processes.</p>",
        "slides.pdf": make_pdf(["Shared memory segments"]),
        "dataset.md": (DATASET / "L5_Tutorial_FIFO_Pipe.md").read_bytes(),
    }
    for name, data in files.items():
        job_url = _upload(client, instructor_headers, data, name).json()["status_url"]
        job = client.get(job_url, headers=instructor_headers).json()
        assert job["status"] == "succeeded", (name, job)
        assert job["result"]["chunk_count"] >= 1


def test_extraction_failures_are_reported_on_the_job(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    body = _upload(client, instructor_headers, b"%PDF-1.4 broken", "broken.pdf").json()
    job = client.get(body["status_url"], headers=instructor_headers).json()
    assert job["status"] == "failed"
    assert job["error"]["code"] == "EXTRACTION_FAILED"
    document = client.get(
        f"{API}/documents/{body['document_id']}", headers=instructor_headers
    ).json()
    assert document["ingestion_status"] == "failed"
    assert document["error_message"]


@pytest.mark.parametrize(
    ("name", "data", "meta", "status", "code"),
    [
        ("lab.docx", MUTEX, {}, 415, "UNSUPPORTED_DOCUMENT_FORMAT"),
        ("fake.pdf", b"not a pdf", {}, 415, "UNSUPPORTED_DOCUMENT_FORMAT"),
        ("big.md", b"x" * (64 * 1024 + 1), {}, 413, "DOCUMENT_TOO_LARGE"),
        ("empty.md", b"", {}, 422, "EMPTY_DOCUMENT"),
        ("ok.md", MUTEX, {"knowledge_base": "tertiary"}, 422, "VALIDATION_FAILED"),
        ("ok.md", MUTEX, {"course_id": "bad id!"}, 422, "VALIDATION_FAILED"),
        ("ok.md", MUTEX, {"unexpected": 1}, 422, "VALIDATION_FAILED"),
    ],
    ids=[
        "docx",
        "fake-pdf",
        "too-large",
        "empty",
        "bad-knowledge-base",
        "bad-course-id",
        "unknown-field",
    ],
)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_invalid_uploads_are_rejected(
    client: TestClient,
    instructor_headers: dict[str, str],
    name: str,
    data: bytes,
    meta: dict,
    status: int,
    code: str,
) -> None:
    _assert_error(_upload(client, instructor_headers, data, name, **meta), status, code)


def test_metadata_must_be_json(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/documents",
        headers=instructor_headers,
        files={"file": ("a.md", MUTEX)},
        data={"metadata": "{not json"},
    )
    _assert_error(response, 422, "VALIDATION_FAILED")


def test_missing_form_parts_are_validation_errors(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/documents", headers=instructor_headers, data={"metadata": _metadata()}
    )
    error = _assert_error(response, 422, "VALIDATION_FAILED")
    assert error["details"]["errors"][0]["location"] == ["body", "file"]


def test_authentication_and_roles(client: TestClient, env: AppEnvironment) -> None:
    error = _assert_error(client.get(f"{API}/documents"), 401, "UNAUTHORIZED")
    assert error["message"]
    assert client.get(f"{API}/documents").headers["WWW-Authenticate"] == "Bearer"
    bad = {"Authorization": "Bearer not-a-token"}
    _assert_error(client.get(f"{API}/documents", headers=bad), 401, "UNAUTHORIZED")
    ghost = {"Authorization": f"Bearer {env.container.tokens.issue(uuid4())}"}
    _assert_error(client.get(f"{API}/documents", headers=ghost), 401, "UNAUTHORIZED")

    _, student_token = env.add_user(UserRole.STUDENT)
    student = {"Authorization": f"Bearer {student_token}"}
    error = _assert_error(_upload(client, student), 403, "FORBIDDEN")
    assert error["details"]["required_roles"] == ["administrator", "instructor"]
    _assert_error(
        client.post(
            f"{API}/courses/operating-systems/retrieval",
            headers=student,
            json={"query": "x"},
        ),
        403,
        "FORBIDDEN",
    )

    _, admin_token = env.add_user(UserRole.ADMINISTRATOR)
    assert (
        _upload(client, {"Authorization": f"Bearer {admin_token}"}).status_code == 202
    )


def test_listing_filters_and_pagination(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    _upload(client, instructor_headers, document_type="tutorial")
    _upload(client, instructor_headers, document_type="lab_task")
    _upload(client, instructor_headers, knowledge_base="supplementary")
    _upload(client, instructor_headers, course_id="networks")

    def total(**params: object) -> int:
        response = client.get(
            f"{API}/documents", headers=instructor_headers, params=params
        )
        assert response.status_code == 200
        return response.json()["total"]

    assert total() == 4
    assert total(course_id="operating-systems") == 3
    assert total(course_id="operating-systems", knowledge_base="supplementary") == 1
    assert total(document_type="lab_task") == 1
    assert total(ingestion_status="indexed") == 4
    page = client.get(
        f"{API}/documents", headers=instructor_headers, params={"limit": 3, "offset": 3}
    ).json()
    assert (len(page["items"]), page["limit"], page["offset"]) == (1, 3, 3)
    _assert_error(
        client.get(
            f"{API}/documents", headers=instructor_headers, params={"limit": 500}
        ),
        422,
        "VALIDATION_FAILED",
    )


def test_metadata_patch(client: TestClient, instructor_headers: dict[str, str]) -> None:
    document_id = _upload(client, instructor_headers).json()["document_id"]
    url = f"{API}/documents/{document_id}/metadata"
    response = client.patch(
        url,
        headers=instructor_headers,
        json={"topic": "threads", "difficulty": "basic"},
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["topic"] == "threads"
    assert response.json()["metadata"]["version"] == "2026"
    _assert_error(
        client.patch(url, headers=instructor_headers, json={}), 422, "VALIDATION_FAILED"
    )
    _assert_error(
        client.patch(url, headers=instructor_headers, json={"course_id": "x"}),
        422,
        "VALIDATION_FAILED",
    )
    _assert_error(
        client.patch(
            f"{API}/documents/{uuid4()}/metadata",
            headers=instructor_headers,
            json={"topic": "x"},
        ),
        404,
        "NOT_FOUND",
    )


def test_course_indexing_and_retrieval_jobs(
    client: TestClient, instructor_headers: dict[str, str]
) -> None:
    _upload(client, instructor_headers)
    _upload(
        client,
        instructor_headers,
        b"# Pipes\nA pipe connects two processes.",
        "pipes.md",
    )

    accepted = client.post(
        f"{API}/courses/operating-systems/index", headers=instructor_headers
    )
    assert accepted.status_code == 202
    job = client.get(accepted.json()["status_url"], headers=instructor_headers).json()
    assert (job["status"], job["result"]["indexed"], job["course_id"]) == (
        "succeeded",
        2,
        "operating-systems",
    )

    accepted = client.post(
        f"{API}/courses/operating-systems/retrieval",
        headers=instructor_headers,
        json={
            "query": "how does a mutex protect a critical section",
            "top_k": 1,
            "purpose": "mandatory",
        },
    )
    assert accepted.status_code == 202
    result = client.get(
        accepted.json()["status_url"], headers=instructor_headers
    ).json()["result"]
    assert result["strategy"] == "vector"
    assert [item["section_path"] for item in result["evidence"]] == [
        ["Synchronization", "Mutex"]
    ]

    _assert_error(
        client.post(f"{API}/courses/unknown-course/index", headers=instructor_headers),
        404,
        "NOT_FOUND",
    )
    _assert_error(
        client.post(
            f"{API}/courses/operating-systems/retrieval",
            headers=instructor_headers,
            json={"query": ""},
        ),
        422,
        "VALIDATION_FAILED",
    )


def test_jobs_are_visible_to_their_owner_and_administrators(
    client: TestClient, env: AppEnvironment, instructor_headers: dict[str, str]
) -> None:
    status_url = _upload(client, instructor_headers).json()["status_url"]
    _, other_token = env.add_user(UserRole.INSTRUCTOR)
    _assert_error(
        client.get(status_url, headers={"Authorization": f"Bearer {other_token}"}),
        404,
        "NOT_FOUND",
    )
    _assert_error(
        client.get(
            f"{status_url}/logs", headers={"Authorization": f"Bearer {other_token}"}
        ),
        404,
        "NOT_FOUND",
    )
    _, admin_token = env.add_user(UserRole.ADMINISTRATOR)
    assert (
        client.get(
            status_url, headers={"Authorization": f"Bearer {admin_token}"}
        ).status_code
        == 200
    )
    _assert_error(
        client.get(f"{API}/jobs/{uuid4()}", headers=instructor_headers),
        404,
        "NOT_FOUND",
    )


def test_queued_jobs_wait_for_the_worker(tmp_path: Path) -> None:
    env = build_environment(tmp_path, inline=False)
    _, token = env.add_user(UserRole.INSTRUCTOR)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(env.container)) as client:
        body = _upload(client, headers).json()
        assert body["ingestion_status"] == "queued"
        assert (
            client.get(body["status_url"], headers=headers).json()["status"] == "queued"
        )


def test_queue_outage_returns_503(tmp_path: Path) -> None:
    env = build_environment(tmp_path, inline=False)
    env.queue.fail = True  # type: ignore[union-attr]
    _, token = env.add_user(UserRole.INSTRUCTOR)
    with TestClient(create_app(env.container)) as client:
        _assert_error(
            _upload(client, {"Authorization": f"Bearer {token}"}),
            503,
            "QUEUE_UNAVAILABLE",
        )


def test_request_ids_are_propagated_and_unknown_routes_use_the_envelope(
    client: TestClient,
) -> None:
    response = client.get(f"{API}/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"
    generated = client.get(
        f"{API}/health", headers={"X-Request-ID": "bad id with spaces"}
    )
    assert generated.headers["X-Request-ID"].startswith("req_")
    _assert_error(client.get(f"{API}/nothing-here"), 404, "NOT_FOUND")


def test_unexpected_errors_return_a_generic_500(tmp_path: Path) -> None:
    env = build_environment(tmp_path)
    _, token = env.add_user(UserRole.INSTRUCTOR)

    def explode(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("database password is hunter2")

    env.container.document_service.list = explode  # type: ignore[method-assign]
    with TestClient(create_app(env.container), raise_server_exceptions=False) as client:
        response = client.get(
            f"{API}/documents", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text


def test_openapi_document_is_published(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert f"{API}/documents" in paths
    assert f"{API}/courses/{{course_id}}/retrieval" in paths
