"""Background jobs: submission (API side) and execution (worker side)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from rag_lab_generator.domain.errors import DomainError
from rag_lab_generator.domain.models import Job, JobStatus, JobType, User
from rag_lab_generator.domain.ports import JobQueue, JobRepository

logger = logging.getLogger(__name__)

JobHandler = Callable[[Job], dict[str, Any]]


class QueueUnavailableError(DomainError):
    code = "QUEUE_UNAVAILABLE"


class JobService:
    def __init__(self, jobs: JobRepository, queue: JobQueue) -> None:
        self._jobs = jobs
        self._queue = queue

    def submit(  # pylint: disable=too-many-arguments
        self,
        job_type: JobType,
        requested_by: User,
        *,
        course_id: str | None = None,
        document_id: UUID | None = None,
        parameters: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Job:
        job = Job(
            job_id=uuid4(),
            job_type=job_type,
            status=JobStatus.QUEUED,
            requested_by=requested_by.user_id,
            created_at=datetime.now(UTC),
            course_id=course_id,
            document_id=document_id,
            parameters=parameters or {},
            request_id=request_id,
        )
        self._jobs.add_job(job)
        self._jobs.add_log(
            job.job_id,
            "info",
            "job.queued",
            f"{job_type} queued",
            {"request_id": request_id} if request_id else None,
        )
        try:
            self._queue.enqueue(job.job_id)
        except Exception as exc:
            logger.exception("Could not enqueue job %s", job.job_id)
            self._jobs.mark_failed(
                job.job_id, QueueUnavailableError.code, "Job queue unavailable."
            )
            raise QueueUnavailableError(
                "The job queue is unavailable; try again later."
            ) from exc
        return self._jobs.get_job(job.job_id)

    def get(self, job_id: UUID) -> Job:
        return self._jobs.get_job(job_id)


class JobRunner:
    """Runs one job and records its state transitions and execution logs."""

    def __init__(
        self, jobs: JobRepository, handlers: Mapping[JobType, JobHandler]
    ) -> None:
        self._jobs = jobs
        self._handlers = handlers

    def run(self, job_id: UUID) -> Job:
        job = self._jobs.get_job(job_id)
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            logger.warning("Job %s is already %s; skipping", job_id, job.status)
            return job
        job = self._jobs.mark_running(job_id)
        self._jobs.add_log(job_id, "info", "job.started", f"{job.job_type} started")
        started = perf_counter()
        try:
            result = self._handlers[job.job_type](job)
        except DomainError as exc:
            self._jobs.add_log(
                job_id,
                "error",
                "job.failed",
                exc.message,
                {"code": exc.code, **exc.details},
            )
            return self._jobs.mark_failed(job_id, exc.code, exc.message)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Every failure must end in a recorded state (NFR-09); the traceback
            # goes to the worker log, not to the client.
            logger.exception("Job %s failed", job_id)
            self._jobs.add_log(
                job_id,
                "error",
                "job.failed",
                "Unexpected error",
                {"exception": type(exc).__name__},
            )
            return self._jobs.mark_failed(
                job_id, "INTERNAL_ERROR", "The job failed because of an internal error."
            )
        duration_ms = round((perf_counter() - started) * 1000, 2)
        self._jobs.add_log(
            job_id,
            "info",
            "job.succeeded",
            f"{job.job_type} succeeded",
            {"duration_ms": duration_ms},
        )
        return self._jobs.mark_succeeded(job_id, result)
