"""SQLAlchemy mapping of the relational schema (Stage 2, Section 9).

Only the tables needed for ingestion, indexing, retrieval, and jobs exist so far;
the assignment, claim, benchmark, and evaluation tables follow with the stages
that use them. Column types fall back to portable equivalents on SQLite so the
repositories can be unit-tested without a PostgreSQL server; production and the
integration tests use PostgreSQL through the Alembic migrations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
TEXT_ARRAY = JSON().with_variant(ARRAY(Text()), "postgresql")
TIMESTAMP_TZ = DateTime(timezone=True)
NOW = text("CURRENT_TIMESTAMP")


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "user_role IN ('instructor', 'student', 'researcher', 'administrator')",
            name="ck_users_user_role",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    user_role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )


class CourseRow(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )


class KnowledgeBaseRow(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "knowledge_base_role IN ('primary', 'supplementary')",
            name="ck_knowledge_bases_role",
        ),
        UniqueConstraint(
            "course_id", "knowledge_base_role", name="uq_knowledge_bases_course_role"
        ),
        Index("idx_knowledge_bases_course", "course_id"),
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("courses.course_id", ondelete="CASCADE")
    )
    knowledge_base_role: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )


class SourceDocumentRow(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint(
            "ingestion_status IN ('queued', 'processing', 'indexed', 'failed')",
            name="ck_source_documents_status",
        ),
        Index("idx_documents_knowledge_base", "knowledge_base_id", "ingestion_status"),
        Index("idx_documents_metadata", "metadata", postgresql_using="gin"),
    )

    document_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_bases.knowledge_base_id")
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.user_id"))
    filename: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(128))
    storage_uri: Mapped[str] = mapped_column(Text, unique=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON_DOCUMENT, default=dict
    )
    ingestion_status: Mapped[str] = mapped_column(String(20), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )


class DocumentChunkRow(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index"),
        CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="ck_document_chunks_page"
        ),
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_position"
        ),
        UniqueConstraint(
            "chroma_collection",
            "chroma_record_id",
            name="uq_document_chunks_chroma_record",
        ),
        Index("idx_chunks_document", "document_id", "chunk_index"),
    )

    chunk_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.document_id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[list[str]] = mapped_column(TEXT_ARRAY, default=list)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON_DOCUMENT, default=dict
    )
    chroma_collection: Mapped[str] = mapped_column(String(256))
    chroma_record_id: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )


class BackgroundJobRow(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('document_ingestion', 'course_indexing', 'retrieval')",
            name="ck_background_jobs_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_background_jobs_status",
        ),
        CheckConstraint(
            "(CASE WHEN course_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN document_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_background_jobs_single_target",
        ),
        Index("idx_jobs_status_created", "status", "created_at"),
    )

    job_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    rq_job_id: Mapped[str] = mapped_column(String(256), unique=True)
    job_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    requested_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.user_id"))
    course_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("courses.course_id")
    )
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.document_id", ondelete="CASCADE")
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    request_id: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_TZ)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_TZ)


class ExecutionLogRow(Base):
    __tablename__ = "execution_logs"
    __table_args__ = (
        CheckConstraint(
            "level IN ('debug', 'info', 'warning', 'error')",
            name="ck_execution_logs_level",
        ),
        Index("idx_execution_logs_job_time", "job_id", "recorded_at"),
    )

    log_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        Identity(always=True),
        primary_key=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("background_jobs.job_id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(String(16))
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_TZ, default=utc_now, server_default=NOW
    )
