"""RQ worker process and its job entry point."""

from __future__ import annotations

import logging
from functools import cache
from uuid import UUID

from redis import Redis
from rq import Queue, SimpleWorker

from rag_lab_generator.application.jobs import JobRunner
from rag_lab_generator.config import get_settings
from rag_lab_generator.container import build_worker_runner

logger = logging.getLogger(__name__)


@cache
def _runner() -> JobRunner:
    return build_worker_runner(get_settings())


def run_job(job_id: str) -> str:
    """Entry point enqueued by the API (see infrastructure.queue.JOB_ENTRY_POINT)."""
    job = _runner().run(UUID(job_id))
    return str(job.status)


def main(burst: bool = False) -> None:
    """Run one worker that executes jobs in its own process.

    SimpleWorker does not fork per job, so the Chroma client and the database
    pool are opened once and reused, and exactly one process writes to the
    persistent vector store.
    """
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.queue_name, connection=connection)
    _runner()  # fail fast on configuration errors before taking jobs
    logger.info("Worker listening on queue %s", settings.queue_name)
    SimpleWorker([queue], connection=connection).work(burst=burst, with_scheduler=False)
