"""Pydantic request and response models of the /api/v1 interface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rag_lab_generator.domain.models import (
    DocumentFilter,
    DocumentMetadata,
    IngestionStatus,
    Job,
    JobStatus,
    JobType,
    KnowledgeBaseRole,
    SourceDocument,
)
from rag_lab_generator.domain.policy import EvidencePurpose

COURSE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"


class DocumentMetadataIn(BaseModel):
    """The JSON `metadata` part of a document upload."""

    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    knowledge_base: KnowledgeBaseRole
    document_type: str | None = Field(default=None, max_length=64)
    topic: str | None = Field(default=None, max_length=256)
    version: str | None = Field(default=None, max_length=64)
    learning_outcomes: list[str] = Field(default_factory=list, max_length=50)
    difficulty: str | None = Field(default=None, max_length=32)
    authority_level: str | None = Field(default=None, max_length=32)

    def to_domain(self) -> DocumentMetadata:
        return DocumentMetadata(
            course_id=self.course_id,
            knowledge_base=self.knowledge_base,
            document_type=self.document_type,
            topic=self.topic,
            version=self.version,
            learning_outcomes=tuple(self.learning_outcomes),
            difficulty=self.difficulty,
            authority_level=self.authority_level,
        )


class DocumentMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str | None = Field(default=None, max_length=64)
    topic: str | None = Field(default=None, max_length=256)
    version: str | None = Field(default=None, max_length=64)
    learning_outcomes: list[str] | None = Field(default=None, max_length=50)
    difficulty: str | None = Field(default=None, max_length=32)
    authority_level: str | None = Field(default=None, max_length=32)


class DocumentUploadAccepted(BaseModel):
    document_id: UUID
    ingestion_status: IngestionStatus
    job_id: UUID
    status_url: str


class DocumentOut(BaseModel):
    document_id: UUID
    course_id: str
    knowledge_base: KnowledgeBaseRole
    filename: str
    media_type: str
    checksum_sha256: str
    metadata: dict[str, Any]
    ingestion_status: IngestionStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, document: SourceDocument) -> DocumentOut:
        return cls(
            document_id=document.document_id,
            course_id=document.course_id,
            knowledge_base=document.knowledge_base,
            filename=document.filename,
            media_type=document.media_type,
            checksum_sha256=document.checksum_sha256,
            metadata=document.metadata,
            ingestion_status=document.ingestion_status,
            error_message=document.error_message,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class DocumentListQuery(BaseModel):
    """Query parameters of GET /documents: filters and pagination."""

    model_config = ConfigDict(extra="forbid")

    course_id: str | None = None
    knowledge_base: KnowledgeBaseRole | None = None
    document_type: str | None = None
    ingestion_status: IngestionStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    def to_filter(self) -> DocumentFilter:
        return DocumentFilter(
            course_id=self.course_id,
            knowledge_bases=(
                frozenset({self.knowledge_base}) if self.knowledge_base else None
            ),
            document_type=self.document_type,
            ingestion_status=self.ingestion_status,
        )


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class JobAccepted(BaseModel):
    job_id: UUID
    status: JobStatus
    status_url: str

    @classmethod
    def from_domain(cls, job: Job) -> JobAccepted:
        return cls(
            job_id=job.job_id, status=job.status, status_url=job_status_url(job.job_id)
        )


class JobError(BaseModel):
    code: str
    message: str


class JobOut(BaseModel):
    job_id: UUID
    job_type: JobType
    status: JobStatus
    course_id: str | None
    document_id: UUID | None
    result: dict[str, Any] | None
    error: JobError | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, job: Job) -> JobOut:
        error = None
        if job.status is JobStatus.FAILED:
            error = JobError(
                code=job.error_code or "UNKNOWN", message=job.error_message or ""
            )
        return cls(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            course_id=job.course_id,
            document_id=job.document_id,
            result=job.result,
            error=error,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


class ExecutionLogOut(BaseModel):
    level: str
    event_type: str
    message: str
    details: dict[str, Any]


class RetrievalRequest(BaseModel):
    """Retrieval preview for instructors and researchers (FR-11, FR-12)."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    purpose: EvidencePurpose = EvidencePurpose.CONTEXT
    document_type: str | None = Field(default=None, max_length=64)
    topic: str | None = Field(default=None, max_length=256)


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, str]


def job_status_url(job_id: UUID) -> str:
    return f"/api/v1/jobs/{job_id}"
