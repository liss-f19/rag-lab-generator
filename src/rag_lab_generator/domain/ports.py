"""Ports: interfaces the application layer needs from the outside world.

Infrastructure adapters implement them (PostgreSQL repositories, Chroma, file
storage, embedding providers, RQ). Tests replace them with in-memory fakes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from rag_lab_generator.domain.models import (
    Chunk,
    DocumentFilter,
    EvidenceCandidate,
    IngestionStatus,
    Job,
    RetrievalQuery,
    SourceDocument,
    TextBlock,
    User,
)
from rag_lab_generator.domain.policy import SourceAuthorityPolicy


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    token_count: int = 0


@dataclass(frozen=True)
class VectorHit:
    record_id: str
    distance: float


@dataclass(frozen=True)
class ExecutionLog:
    level: str
    event_type: str
    message: str
    details: dict[str, Any]


class UserRepository(Protocol):
    def add_user(self, user: User) -> None: ...

    def get_user(self, user_id: UUID) -> User | None: ...

    def get_user_by_email(self, email: str) -> User | None: ...


class DocumentRepository(Protocol):
    def add_document(self, document: SourceDocument) -> None: ...

    def get_document(self, document_id: UUID) -> SourceDocument: ...

    def list_documents(
        self, doc_filter: DocumentFilter, limit: int, offset: int
    ) -> tuple[list[SourceDocument], int]: ...

    def update_metadata(
        self, document_id: UUID, fields: dict[str, Any]
    ) -> SourceDocument: ...

    def set_ingestion_status(
        self,
        document_id: UUID,
        status: IngestionStatus,
        error_message: str | None = None,
    ) -> None: ...

    def replace_chunks(self, document_id: UUID, chunks: Sequence[Chunk]) -> None: ...

    def list_chunks(self, document_id: UUID) -> list[Chunk]: ...

    def get_chunks(self, chunk_ids: Sequence[UUID]) -> dict[UUID, Chunk]: ...


class JobRepository(Protocol):
    def add_job(self, job: Job) -> None: ...

    def get_job(self, job_id: UUID) -> Job: ...

    def mark_running(self, job_id: UUID) -> Job: ...

    def mark_succeeded(self, job_id: UUID, result: dict[str, Any]) -> Job: ...

    def mark_failed(self, job_id: UUID, error_code: str, error_message: str) -> Job: ...

    def add_log(
        self,
        job_id: UUID,
        level: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None: ...

    def list_logs(self, job_id: UUID) -> list[ExecutionLog]: ...


class FileStorage(Protocol):
    def save(self, data: bytes, suffix: str) -> str: ...

    def read(self, uri: str) -> bytes: ...

    def delete(self, uri: str) -> None: ...


class TextExtractor(Protocol):
    def extract(self, data: bytes) -> list[TextBlock]: ...


class EmbeddingClient(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch: ...


class VectorIndex(Protocol):
    def upsert(
        self,
        collection: str,
        record_ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, str | int | float | bool]],
    ) -> None: ...

    def delete_document(self, collection: str, document_id: UUID) -> None: ...

    def query(
        self,
        collection: str,
        embedding: Sequence[float],
        top_k: int,
        document_ids: Sequence[UUID],
    ) -> list[VectorHit]: ...


class JobQueue(Protocol):
    def enqueue(self, job_id: UUID) -> None: ...


class RetrievalStrategy(Protocol):
    name: str

    def retrieve(
        self,
        query: RetrievalQuery,
        policy: SourceAuthorityPolicy,
        top_k: int,
    ) -> list[EvidenceCandidate]: ...
