"""Job submission and execution: state transitions and execution logs."""

import pytest
from sqlalchemy import select

from rag_lab_generator.application.jobs import (
    JobRunner,
    JobService,
    QueueUnavailableError,
)
from rag_lab_generator.domain.errors import ExtractionError
from rag_lab_generator.domain.models import (
    JobStatus,
    JobType,
    KnowledgeBaseRole,
    UserRole,
)
from rag_lab_generator.infrastructure.orm import BackgroundJobRow
from tests.conftest import AppEnvironment
from tests.fakes import RecordingQueue


def _submit(env: AppEnvironment, queue: RecordingQueue) -> tuple[JobService, object]:
    user, _ = env.add_user(UserRole.INSTRUCTOR)
    document = env.add_document("sop", KnowledgeBaseRole.PRIMARY)
    service = JobService(env.container.jobs, queue)
    job = service.submit(
        JobType.DOCUMENT_INGESTION,
        user,
        document_id=document.document_id,
        request_id="req_x",
    )
    return service, job


def test_submit_stores_a_queued_job_and_enqueues_it(env: AppEnvironment) -> None:
    queue = RecordingQueue()
    service, job = _submit(env, queue)
    assert job.status is JobStatus.QUEUED
    assert job.request_id == "req_x"
    assert queue.enqueued == [job.job_id]
    assert service.get(job.job_id) == job
    logs = env.container.jobs.list_logs(job.job_id)
    assert [(log.event_type, log.details) for log in logs] == [
        ("job.queued", {"request_id": "req_x"})
    ]


def test_submit_fails_the_job_when_the_queue_is_down(env: AppEnvironment) -> None:
    with pytest.raises(QueueUnavailableError):
        _submit(env, RecordingQueue(fail=True))
    with env.container.engine.connect() as connection:
        rows = connection.execute(
            select(BackgroundJobRow.status, BackgroundJobRow.error_code)
        )
        assert rows.all() == [("failed", "QUEUE_UNAVAILABLE")]


def _runner(env: AppEnvironment, handler) -> JobRunner:  # type: ignore[no-untyped-def]
    return JobRunner(env.container.jobs, {JobType.DOCUMENT_INGESTION: handler})


def test_runner_records_success(env: AppEnvironment) -> None:
    _, job = _submit(env, RecordingQueue())
    finished = _runner(env, lambda job: {"chunk_count": 3}).run(job.job_id)
    assert finished.status is JobStatus.SUCCEEDED
    assert finished.result == {"chunk_count": 3}
    assert finished.started_at is not None and finished.completed_at is not None
    events = [log.event_type for log in env.container.jobs.list_logs(job.job_id)]
    assert events == ["job.queued", "job.started", "job.succeeded"]


def test_runner_records_domain_errors_with_their_code(env: AppEnvironment) -> None:
    _, job = _submit(env, RecordingQueue())

    def fail(_job):  # type: ignore[no-untyped-def]
        raise ExtractionError("The PDF file is damaged.", details={"page": 2})

    finished = _runner(env, fail).run(job.job_id)
    assert (finished.status, finished.error_code) == (
        JobStatus.FAILED,
        "EXTRACTION_FAILED",
    )
    last = env.container.jobs.list_logs(job.job_id)[-1]
    assert last.details == {"code": "EXTRACTION_FAILED", "page": 2}


def test_runner_hides_unexpected_errors_from_clients(env: AppEnvironment) -> None:
    _, job = _submit(env, RecordingQueue())

    def crash(_job):  # type: ignore[no-untyped-def]
        raise KeyError("secret internal detail")

    finished = _runner(env, crash).run(job.job_id)
    assert finished.error_code == "INTERNAL_ERROR"
    assert "secret" not in (finished.error_message or "")


def test_runner_does_not_rerun_finished_jobs(env: AppEnvironment) -> None:
    _, job = _submit(env, RecordingQueue())
    calls = []
    runner = _runner(env, lambda job: calls.append(job) or {})
    runner.run(job.job_id)
    runner.run(job.job_id)
    assert len(calls) == 1
