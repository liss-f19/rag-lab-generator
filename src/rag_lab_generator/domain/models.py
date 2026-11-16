"""Domain entities and value objects.

This module depends on the Python standard library only (see the layer rules in
the project report, Table "Layers and dependency rules").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class UserRole(StrEnum):
    INSTRUCTOR = "instructor"
    STUDENT = "student"
    RESEARCHER = "researcher"
    ADMINISTRATOR = "administrator"


class KnowledgeBaseRole(StrEnum):
    PRIMARY = "primary"
    SUPPLEMENTARY = "supplementary"


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class JobType(StrEnum):
    DOCUMENT_INGESTION = "document_ingestion"
    COURSE_INDEXING = "course_indexing"
    RETRIEVAL = "retrieval"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class User:
    user_id: UUID
    email: str
    display_name: str
    role: UserRole


@dataclass(frozen=True)
class DocumentMetadata:  # pylint: disable=too-many-instance-attributes
    """Descriptive metadata of a source document (FR-04)."""

    course_id: str
    knowledge_base: KnowledgeBaseRole
    document_type: str | None = None
    topic: str | None = None
    version: str | None = None
    learning_outcomes: tuple[str, ...] = ()
    difficulty: str | None = None
    authority_level: str | None = None

    def descriptive_fields(self) -> dict[str, Any]:
        """Fields stored in the JSON metadata column (course and base have columns)."""
        return {
            "document_type": self.document_type,
            "topic": self.topic,
            "version": self.version,
            "learning_outcomes": list(self.learning_outcomes),
            "difficulty": self.difficulty,
            "authority_level": self.authority_level,
        }


@dataclass(frozen=True)
class SourceDocument:  # pylint: disable=too-many-instance-attributes
    document_id: UUID
    course_id: str
    knowledge_base: KnowledgeBaseRole
    filename: str
    media_type: str
    storage_uri: str
    checksum_sha256: str
    metadata: dict[str, Any]
    ingestion_status: IngestionStatus
    uploaded_by: UUID | None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    chunk_count: int = 0


@dataclass(frozen=True)
class TextBlock:
    """A piece of extracted text with its position in the source (FR-03, FR-07)."""

    text: str
    section_path: tuple[str, ...] = ()
    page_number: int | None = None


@dataclass(frozen=True)
class Chunk:  # pylint: disable=too-many-instance-attributes
    """An indexed fragment; its row in document_chunks is the evidence anchor."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    section_path: tuple[str, ...]
    page_number: int | None
    chroma_collection: str
    chroma_record_id: str

    def embedding_text(self) -> str:
        """Text sent to the embedding model: the section breadcrumb gives context."""
        if not self.section_path:
            return self.content
        return " > ".join(self.section_path) + "\n\n" + self.content


@dataclass(frozen=True)
class Job:  # pylint: disable=too-many-instance-attributes
    job_id: UUID
    job_type: JobType
    status: JobStatus
    requested_by: UUID
    created_at: datetime
    course_id: str | None = None
    document_id: UUID | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class DocumentFilter:
    """Metadata filters for listing documents and for retrieval (FR-11)."""

    course_id: str | None = None
    knowledge_bases: frozenset[KnowledgeBaseRole] | None = None
    document_type: str | None = None
    topic: str | None = None
    ingestion_status: IngestionStatus | None = None


@dataclass(frozen=True)
class RetrievalQuery:
    course_id: str
    text: str
    document_type: str | None = None
    topic: str | None = None


def vector_collection_name(course_id: str, embedding_model: str) -> str:
    """One vector collection per course and embedding model.

    Vectors of different models are never mixed, and changing the model creates a
    new collection instead of corrupting the old one. The name satisfies Chroma's
    rules: 3-512 characters from [a-zA-Z0-9._-], alphanumeric at both ends.
    """
    raw = f"{course_id}--{embedding_model}"
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-._")[:512].strip("-._")
    return name if len(name) >= 3 else f"col-{name}-x"


@dataclass(frozen=True)
class EvidenceCandidate:  # pylint: disable=too-many-instance-attributes
    """A retrieved passage; chunk_id always points to a row in document_chunks."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    knowledge_base: KnowledgeBaseRole
    excerpt: str
    section_path: tuple[str, ...]
    page_number: int | None
    similarity: float
    score: float
