"""Infrastructure adapters: file storage, Chroma, RQ queue, tokens, settings."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import fakeredis
import pytest
from pydantic import ValidationError
from rq import Queue

from rag_lab_generator.config import Settings
from rag_lab_generator.container import build_container, build_embedder
from rag_lab_generator.infrastructure.chroma_index import ChromaVectorIndex
from rag_lab_generator.infrastructure.embeddings import (
    HashingEmbeddingClient,
    OpenAIEmbeddingClient,
)
from rag_lab_generator.infrastructure.files import LocalFileStorage
from rag_lab_generator.infrastructure.queue import (
    JOB_ENTRY_POINT,
    InlineJobQueue,
    RQJobQueue,
)
from rag_lab_generator.infrastructure.security import InvalidTokenError, TokenService
from tests.conftest import SIGNING_KEY, make_settings


def test_file_storage_round_trip_and_path_safety(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "files")
    uri = storage.save(b"content", ".md")
    assert uri.startswith("file://") and uri.endswith(".md")
    assert storage.read(uri) == b"content"
    storage.delete(uri)
    storage.delete(uri)  # deleting twice is harmless
    with pytest.raises(FileNotFoundError):
        storage.read(uri)
    with pytest.raises(ValueError):
        storage.read("file://../../outside.txt")
    with pytest.raises(ValueError):
        storage.read("s3://bucket/key")


def test_unsafe_suffixes_are_dropped(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    uri = storage.save(b"x", "/../../evil")
    assert "evil" not in uri and ".." not in uri


def test_chroma_index_upserts_queries_and_deletes(tmp_path: Path) -> None:
    index = ChromaVectorIndex(tmp_path / "chroma")
    first, second = uuid4(), uuid4()
    index.upsert(
        "sop--test",
        ["a", "b", "c"],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
        [
            {"document_id": str(first)},
            {"document_id": str(first)},
            {"document_id": str(second)},
        ],
    )
    hits = index.query("sop--test", [1.0, 0.0, 0.0], 3, [first, second])
    assert [hit.record_id for hit in hits] == ["a", "c", "b"]
    assert hits[0].distance == pytest.approx(0.0, abs=1e-6)
    assert [
        hit.record_id for hit in index.query("sop--test", [1.0, 0.0, 0.0], 3, [second])
    ] == ["c"]

    index.delete_document("sop--test", first)
    assert index.count("sop--test") == 1
    assert index.query("missing-collection", [1.0, 0.0, 0.0], 3, [second]) == []
    assert index.query("sop--test", [1.0, 0.0, 0.0], 3, []) == []
    index.delete_document("missing-collection", first)
    index.upsert("sop--test", [], [], [])
    assert index.count("missing-collection") == 0


def test_rq_queue_enqueues_the_worker_entry_point() -> None:
    connection = fakeredis.FakeRedis()
    job_id = uuid4()
    queue = RQJobQueue(connection, "rag-test", job_timeout_seconds=600)
    queue.enqueue(job_id)
    queue.ping()
    rq_job = Queue("rag-test", connection=connection).fetch_job(str(job_id))
    assert rq_job is not None
    assert rq_job.func_name == JOB_ENTRY_POINT
    assert rq_job.args == (str(job_id),)
    assert rq_job.timeout == 600


def test_inline_queue_runs_immediately() -> None:
    seen = []
    queue = InlineJobQueue(seen.append)
    job_id = uuid4()
    queue.enqueue(job_id)
    queue.ping()
    assert seen == [job_id]


def test_tokens_verify_and_reject_tampering() -> None:
    service = TokenService(SIGNING_KEY, ttl_minutes=5)
    user_id = uuid4()
    token = service.issue(user_id)
    assert service.verify(token) == user_id
    with pytest.raises(InvalidTokenError):
        TokenService("another-key-" + "y" * 32, 5).verify(token)
    with pytest.raises(InvalidTokenError):
        service.verify(token[:-2] + "xx")
    expired = service.issue(user_id, now=datetime.now(UTC) - timedelta(minutes=10))
    with pytest.raises(InvalidTokenError):
        service.verify(expired)


def test_settings_require_a_strong_signing_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        make_settings(tmp_path, token_signing_key="short")
    assert make_settings(tmp_path).queue_backend == "inline"


def test_embedder_selection(tmp_path: Path) -> None:
    assert isinstance(build_embedder(make_settings(tmp_path)), HashingEmbeddingClient)
    with pytest.raises(RuntimeError):
        build_embedder(make_settings(tmp_path, embedding_provider="openai"))
    openai_settings = make_settings(
        tmp_path, embedding_provider="openai", openai_api_key="sk-test"
    )
    assert isinstance(build_embedder(openai_settings), OpenAIEmbeddingClient)


def test_container_builds_for_both_queue_backends(tmp_path: Path) -> None:
    inline = build_container(make_settings(tmp_path))
    assert isinstance(inline.queue, InlineJobQueue)
    rq_settings: Settings = make_settings(
        tmp_path, queue_backend="rq", redis_url="redis://localhost:1/0"
    )
    assert isinstance(build_container(rq_settings).queue, RQJobQueue)
