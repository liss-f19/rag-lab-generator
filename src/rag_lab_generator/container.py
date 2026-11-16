"""Composition root: builds the adapters and services for the API and the worker."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Protocol
from uuid import UUID

from redis import Redis
from sqlalchemy import Engine

from rag_lab_generator.application.documents import DocumentService
from rag_lab_generator.application.jobs import JobRunner, JobService
from rag_lab_generator.config import Settings
from rag_lab_generator.domain.errors import InvalidRequestError
from rag_lab_generator.domain.models import Job, JobType
from rag_lab_generator.domain.ports import (
    DocumentRepository,
    EmbeddingClient,
    FileStorage,
    JobRepository,
    VectorIndex,
)
from rag_lab_generator.infrastructure.db import create_db_engine, create_session_factory
from rag_lab_generator.infrastructure.embeddings import (
    HashingEmbeddingClient,
    OpenAIEmbeddingClient,
)
from rag_lab_generator.infrastructure.files import LocalFileStorage
from rag_lab_generator.infrastructure.queue import InlineJobQueue, RQJobQueue
from rag_lab_generator.infrastructure.repositories import (
    SqlDocumentRepository,
    SqlJobRepository,
    SqlUserRepository,
)
from rag_lab_generator.infrastructure.security import TokenService
from rag_lab_generator.ingestion.chunking import StructuredChunker
from rag_lab_generator.ingestion.service import IngestionService
from rag_lab_generator.retrieval.service import RetrievalService
from rag_lab_generator.retrieval.vector import VectorRetrievalStrategy


class PingableQueue(Protocol):
    def enqueue(self, job_id: UUID) -> None: ...

    def ping(self) -> None: ...


@dataclass
class Container:  # pylint: disable=too-many-instance-attributes
    settings: Settings
    engine: Engine
    users: SqlUserRepository
    documents: SqlDocumentRepository
    jobs: SqlJobRepository
    files: LocalFileStorage
    tokens: TokenService
    queue: PingableQueue
    job_service: JobService
    document_service: DocumentService


def build_embedder(settings: Settings) -> EmbeddingClient:
    if settings.embedding_provider == "hashing":
        return HashingEmbeddingClient(settings.hashing_dimensions)
    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
    return OpenAIEmbeddingClient(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        timeout_seconds=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
        base_url=settings.openai_base_url,
    )


def build_job_runner(  # pylint: disable=too-many-arguments
    settings: Settings,
    *,
    documents: DocumentRepository,
    jobs: JobRepository,
    files: FileStorage,
    index: VectorIndex,
    embedder: EmbeddingClient,
) -> JobRunner:
    ingestion = IngestionService(
        documents=documents,
        files=files,
        chunker=StructuredChunker(
            settings.chunk_max_chars, settings.chunk_overlap_chars
        ),
        embedder=embedder,
        index=index,
    )
    retrieval = RetrievalService(
        VectorRetrievalStrategy(documents=documents, embedder=embedder, index=index),
        embedder.model_id,
    )

    def ingest(job: Job) -> dict[str, object]:
        if job.document_id is None:
            raise InvalidRequestError("Ingestion job without a document.")
        return ingestion.ingest(job.document_id)

    def index_course(job: Job) -> dict[str, object]:
        if job.course_id is None:
            raise InvalidRequestError("Indexing job without a course.")
        return ingestion.index_course(job.course_id)

    def retrieve(job: Job) -> dict[str, object]:
        if job.course_id is None:
            raise InvalidRequestError("Retrieval job without a course.")
        return retrieval.run(job.course_id, job.parameters)

    return JobRunner(
        jobs,
        {
            JobType.DOCUMENT_INGESTION: ingest,
            JobType.COURSE_INDEXING: index_course,
            JobType.RETRIEVAL: retrieve,
        },
    )


def build_worker_runner(settings: Settings) -> JobRunner:
    # Imported here so that the API process never loads Chroma in RQ mode.
    # pylint: disable-next=import-outside-toplevel
    from rag_lab_generator.infrastructure.chroma_index import ChromaVectorIndex

    sessions = create_session_factory(create_db_engine(settings.database_url))
    return build_job_runner(
        settings,
        documents=SqlDocumentRepository(sessions),
        jobs=SqlJobRepository(sessions),
        files=LocalFileStorage(settings.file_storage_dir),
        index=ChromaVectorIndex(settings.chroma_persist_directory),
        embedder=build_embedder(settings),
    )


def _default_queue(settings: Settings) -> PingableQueue:
    if settings.queue_backend == "inline":

        @cache
        def runner() -> JobRunner:
            # Chroma is opened on the first job, not at start-up.
            return build_worker_runner(settings)

        return InlineJobQueue(lambda job_id: runner().run(job_id))
    return RQJobQueue(
        Redis.from_url(settings.redis_url),
        settings.queue_name,
        settings.job_timeout_seconds,
    )


def build_container(
    settings: Settings,
    *,
    engine: Engine | None = None,
    queue: PingableQueue | None = None,
) -> Container:
    """Wire the API-side services; tests may supply their own engine and queue."""
    engine = engine or create_db_engine(settings.database_url)
    sessions = create_session_factory(engine)
    documents = SqlDocumentRepository(sessions)
    jobs = SqlJobRepository(sessions)
    files = LocalFileStorage(settings.file_storage_dir)
    queue = queue or _default_queue(settings)
    job_service = JobService(jobs, queue)
    return Container(
        settings=settings,
        engine=engine,
        users=SqlUserRepository(sessions),
        documents=documents,
        jobs=jobs,
        files=files,
        tokens=TokenService(
            settings.token_signing_key.get_secret_value(), settings.token_ttl_minutes
        ),
        queue=queue,
        job_service=job_service,
        document_service=DocumentService(
            documents=documents,
            files=files,
            jobs=job_service,
            max_upload_bytes=settings.max_upload_bytes,
        ),
    )
