"""SQL repositories, exercised on SQLite (the same code runs on PostgreSQL in CI)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from rag_lab_generator.domain.errors import NotFoundError
from rag_lab_generator.domain.models import (
    Chunk,
    DocumentFilter,
    IngestionStatus,
    Job,
    JobStatus,
    JobType,
    KnowledgeBaseRole,
    UserRole,
)
from tests.conftest import AppEnvironment


def test_documents_create_courses_and_knowledge_bases_on_demand(
    env: AppEnvironment,
) -> None:
    first = env.add_document(
        "sop1", KnowledgeBaseRole.PRIMARY, document_type="tutorial"
    )
    env.add_document("sop1", KnowledgeBaseRole.PRIMARY, document_type="lab_task")
    env.add_document("sop1", KnowledgeBaseRole.SUPPLEMENTARY, document_type="tutorial")
    env.add_document(
        "sop2", KnowledgeBaseRole.PRIMARY, document_type="tutorial", topic="pipes"
    )

    stored = env.container.documents.get_document(first.document_id)
    assert stored.course_id == "sop1"
    assert stored.knowledge_base is KnowledgeBaseRole.PRIMARY
    assert stored.metadata["document_type"] == "tutorial"
    assert stored.chunk_count == 0

    repo = env.container.documents
    assert repo.list_documents(DocumentFilter(course_id="sop1"), 10, 0)[1] == 3
    primary = DocumentFilter(
        course_id="sop1", knowledge_bases=frozenset({KnowledgeBaseRole.PRIMARY})
    )
    assert repo.list_documents(primary, 10, 0)[1] == 2
    tutorials = DocumentFilter(document_type="tutorial")
    assert repo.list_documents(tutorials, 10, 0)[1] == 3
    assert repo.list_documents(DocumentFilter(topic="pipes"), 10, 0)[1] == 1
    page, total = repo.list_documents(DocumentFilter(), limit=2, offset=2)
    assert total == 4 and len(page) == 2


def test_status_metadata_and_chunks_round_trip(env: AppEnvironment) -> None:
    repo = env.container.documents
    document = env.add_document("sop1", KnowledgeBaseRole.PRIMARY)
    chunks = [
        Chunk(
            uuid4(),
            document.document_id,
            position,
            f"text {position}",
            ("A", "B"),
            None,
            "col",
            str(uuid4()),
        )
        for position in range(3)
    ]
    repo.replace_chunks(document.document_id, chunks)
    repo.set_ingestion_status(document.document_id, IngestionStatus.INDEXED)
    updated = repo.update_metadata(document.document_id, {"topic": "threads"})

    assert updated.chunk_count == 3
    assert updated.ingestion_status is IngestionStatus.INDEXED
    assert updated.metadata["topic"] == "threads"
    assert [chunk.content for chunk in repo.list_chunks(document.document_id)] == [
        "text 0",
        "text 1",
        "text 2",
    ]
    fetched = repo.get_chunks([chunks[1].chunk_id, uuid4()])
    assert list(fetched) == [chunks[1].chunk_id]
    assert fetched[chunks[1].chunk_id].section_path == ("A", "B")
    assert repo.get_chunks([]) == {}

    repo.replace_chunks(document.document_id, chunks[:1])
    assert repo.get_document(document.document_id).chunk_count == 1

    indexed = DocumentFilter(ingestion_status=IngestionStatus.INDEXED)
    assert repo.list_documents(indexed, 10, 0)[1] == 1


def test_missing_documents_raise_not_found(env: AppEnvironment) -> None:
    repo = env.container.documents
    missing = uuid4()
    for call in (
        lambda: repo.get_document(missing),
        lambda: repo.update_metadata(missing, {"topic": "x"}),
        lambda: repo.set_ingestion_status(missing, IngestionStatus.FAILED),
    ):
        with pytest.raises(NotFoundError):
            call()


def test_jobs_record_transitions_and_logs(env: AppEnvironment) -> None:
    user, _ = env.add_user(UserRole.INSTRUCTOR)
    document = env.add_document("sop1", KnowledgeBaseRole.PRIMARY)
    jobs = env.container.jobs
    job = Job(
        job_id=uuid4(),
        job_type=JobType.DOCUMENT_INGESTION,
        status=JobStatus.QUEUED,
        requested_by=user.user_id,
        created_at=datetime.now(UTC),
        document_id=document.document_id,
        parameters={"k": 1},
        request_id="req_1",
    )
    jobs.add_job(job)
    assert jobs.mark_running(job.job_id).started_at is not None
    done = jobs.mark_succeeded(job.job_id, {"chunk_count": 4})
    assert done.status is JobStatus.SUCCEEDED and done.result == {"chunk_count": 4}
    failed = jobs.mark_failed(job.job_id, "EXTRACTION_FAILED", "bad file")
    assert (failed.error_code, failed.error_message) == (
        "EXTRACTION_FAILED",
        "bad file",
    )
    assert jobs.get_job(job.job_id).parameters == {"k": 1}

    jobs.add_log(job.job_id, "info", "job.started", "started")
    jobs.add_log(job.job_id, "error", "job.failed", "bad file", {"code": "X"})
    assert [(log.event_type, log.details) for log in jobs.list_logs(job.job_id)] == [
        ("job.started", {}),
        ("job.failed", {"code": "X"}),
    ]
    with pytest.raises(NotFoundError):
        jobs.get_job(uuid4())


def test_users_are_found_by_id_and_email(env: AppEnvironment) -> None:
    user, _ = env.add_user(UserRole.RESEARCHER)
    users = env.container.users
    assert users.get_user(user.user_id) == user
    assert users.get_user_by_email(user.email) == user
    assert users.get_user(uuid4()) is None
    assert users.get_user_by_email("nobody@example.edu") is None
