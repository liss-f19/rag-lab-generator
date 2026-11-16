"""JobQueue adapters: RQ on Redis, and an in-process queue for development."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from redis import Redis
from rq import Queue

JOB_ENTRY_POINT = "rag_lab_generator.worker.run_job"


class RQJobQueue:
    """Enqueues the worker entry point by import path; the job id is the RQ id."""

    def __init__(
        self, connection: Redis, queue_name: str, job_timeout_seconds: int
    ) -> None:
        self._queue = Queue(queue_name, connection=connection)
        self._job_timeout = job_timeout_seconds

    def enqueue(self, job_id: UUID) -> None:
        self._queue.enqueue(
            JOB_ENTRY_POINT,
            str(job_id),
            job_id=str(job_id),
            job_timeout=self._job_timeout,
            result_ttl=3600,
            failure_ttl=7 * 24 * 3600,
        )

    def ping(self) -> None:
        self._queue.connection.ping()


class InlineJobQueue:
    """Runs the job immediately in the calling process.

    For local development without Redis and for tests. In this mode the API
    process also opens the vector store, so no separate worker may run.
    """

    def __init__(self, run: Callable[[UUID], object]) -> None:
        self._run = run

    def enqueue(self, job_id: UUID) -> None:
        self._run(job_id)

    def ping(self) -> None:
        return None
