"""End-to-end on the production stack: PostgreSQL, RQ, the worker, and Chroma."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine, func, select

from rag_lab_generator import worker
from rag_lab_generator.api.app import create_app
from rag_lab_generator.config import get_settings
from rag_lab_generator.container import Container, build_container
from rag_lab_generator.domain.models import DocumentFilter, User, UserRole
from rag_lab_generator.infrastructure.orm import Base, DocumentChunkRow
from tests.conftest import set_environment_variables

pytestmark = pytest.mark.integration

DATASET = Path(__file__).resolve().parents[2] / "dataset"
API = "/api/v1"
SOURCES = [
    "L4_Tutorial_Synchronization.md",
    "L5_Tutorial_FIFO_Pipe.md",
    "L6_Tutorial_Shared_Memory.md",
]


def test_migrations_produce_the_mapped_schema(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()
    assert not differences, differences


@pytest.fixture(name="stack")
def stack_fixture(
    migrated_database: str,
    redis_connection: Redis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Container]:
    """API container and worker configured from the same environment."""
    set_environment_variables(
        monkeypatch,
        tmp_path,
        DATABASE_URL=migrated_database,
        QUEUE_BACKEND="rq",
        QUEUE_NAME="rag-lab-test",
    )
    monkeypatch.setattr("redis.Redis.from_url", lambda url: redis_connection)
    get_settings.cache_clear()
    worker._runner.cache_clear()  # pylint: disable=protected-access
    container = build_container(get_settings())
    yield container
    container.engine.dispose()
    worker._runner.cache_clear()  # pylint: disable=protected-access
    get_settings.cache_clear()


def _instructor_headers(container: Container) -> dict[str, str]:
    user = User(
        user_id=uuid4(),
        email="instructor@pw.edu.pl",
        display_name="Instructor",
        role=UserRole.INSTRUCTOR,
    )
    container.users.add_user(user)
    return {"Authorization": f"Bearer {container.tokens.issue(user.user_id)}"}


def _upload_sources(client: TestClient, headers: dict[str, str]) -> list[dict]:
    accepted = []
    for name in SOURCES:
        response = client.post(
            f"{API}/documents",
            headers=headers,
            files={"file": (name, (DATASET / name).read_bytes())},
            data={"metadata": '{"course_id": "sop2", "knowledge_base": "primary"}'},
        )
        assert response.status_code == 202, response.text
        assert response.json()["ingestion_status"] == "queued"
        accepted.append(response.json())
    return accepted


def _stored_chunk_count(container: Container) -> int:
    count = func.count()  # pylint: disable=not-callable
    with container.engine.connect() as connection:
        statement = select(count).select_from(DocumentChunkRow)
        return int(connection.execute(statement).scalar() or 0)


def test_upload_index_and_retrieve_through_the_worker(stack: Container) -> None:
    headers = _instructor_headers(stack)
    with TestClient(create_app(stack)) as client:
        checks = client.get(f"{API}/health").json()["checks"]
        assert checks == {"database": "ok", "queue": "ok"}
        accepted = _upload_sources(client, headers)

        worker.main(burst=True)

        total_chunks = 0
        for item in accepted:
            job = client.get(item["status_url"], headers=headers).json()
            assert job["status"] == "succeeded", job
            total_chunks += job["result"]["chunk_count"]
            url = f"{API}/documents/{item['document_id']}"
            assert (
                client.get(url, headers=headers).json()["ingestion_status"] == "indexed"
            )
        assert _stored_chunk_count(stack) == total_chunks > 10

        query = "How do I create a FIFO with mkfifo and open it for reading?"
        retrieval = client.post(
            f"{API}/courses/sop2/retrieval",
            headers=headers,
            json={"query": query, "top_k": 3},
        ).json()
        worker.main(burst=True)
        result = client.get(retrieval["status_url"], headers=headers).json()["result"]

    assert len(result["evidence"]) == 3
    assert result["evidence"][0]["filename"] == "L5_Tutorial_FIFO_Pipe.md"
    assert result["evidence"][0]["section_path"]

    # Data survives a restart of the API process (NFR-08).
    restarted = build_container(get_settings())
    documents, total = restarted.document_service.list(
        DocumentFilter(course_id="sop2"), 10, 0
    )
    assert total == 3
    assert sum(document.chunk_count for document in documents) == total_chunks
    restarted.engine.dispose()
