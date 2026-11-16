"""Ingestion, indexing, and job tables.

Implements the part of the planned schema (Stage 2, Section 9) needed for
document ingestion, indexing, retrieval, and background jobs. Differences from
the plan: background_jobs gains parameters, result, and request_id; job types
are limited to the implemented ones (document_ingestion, course_indexing,
retrieval); the single-target check covers the existing target columns.

Revision ID: 0001
Revises:
Create Date: 2026-11-16
"""

# Alembic's file and variable names are fixed.
# pylint: disable=invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("CURRENT_TIMESTAMP")
EMPTY_JSON = sa.text("'{}'::jsonb")


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("user_role", sa.String(20), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "user_role IN ('instructor', 'student', 'researcher', 'administrator')",
            name="ck_users_user_role",
        ),
    )
    op.create_table(
        "courses",
        sa.Column("course_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        _created_at(),
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("knowledge_base_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.course_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("knowledge_base_role", sa.String(20), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "knowledge_base_role IN ('primary', 'supplementary')",
            name="ck_knowledge_bases_role",
        ),
        sa.UniqueConstraint(
            "course_id", "knowledge_base_role", name="uq_knowledge_bases_course_role"
        ),
    )
    op.create_index("idx_knowledge_bases_course", "knowledge_bases", ["course_id"])

    op.create_table(
        "source_documents",
        sa.Column("document_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_bases.knowledge_base_id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by", sa.Uuid(), sa.ForeignKey("users.user_id"), nullable=True
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False, unique=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=EMPTY_JSON),
        sa.Column(
            "ingestion_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW
        ),
        sa.CheckConstraint(
            "ingestion_status IN ('queued', 'processing', 'indexed', 'failed')",
            name="ck_source_documents_status",
        ),
    )
    op.create_index(
        "idx_documents_knowledge_base",
        "source_documents",
        ["knowledge_base_id", "ingestion_status"],
    )
    op.create_index(
        "idx_documents_metadata",
        "source_documents",
        ["metadata"],
        postgresql_using="gin",
    )

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("source_documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "section_path",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("metadata", JSONB(), nullable=False, server_default=EMPTY_JSON),
        sa.Column("chroma_collection", sa.String(256), nullable=False),
        sa.Column("chroma_record_id", sa.String(256), nullable=False),
        _created_at(),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="ck_document_chunks_page"
        ),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_position"
        ),
        sa.UniqueConstraint(
            "chroma_collection",
            "chroma_record_id",
            name="uq_document_chunks_chroma_record",
        ),
    )
    op.create_index(
        "idx_chunks_document", "document_chunks", ["document_id", "chunk_index"]
    )

    op.create_table(
        "background_jobs",
        sa.Column("job_id", sa.Uuid(), primary_key=True),
        sa.Column("rq_job_id", sa.String(256), nullable=False, unique=True),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "requested_by", sa.Uuid(), sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.course_id"),
            nullable=True,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("source_documents.document_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("parameters", JSONB(), nullable=False, server_default=EMPTY_JSON),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('document_ingestion', 'course_indexing', 'retrieval')",
            name="ck_background_jobs_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_background_jobs_status",
        ),
        sa.CheckConstraint(
            "(CASE WHEN course_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN document_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_background_jobs_single_target",
        ),
    )
    op.create_index(
        "idx_jobs_status_created", "background_jobs", ["status", "created_at"]
    )

    op.create_table(
        "execution_logs",
        sa.Column(
            "log_id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("background_jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", JSONB(), nullable=False, server_default=EMPTY_JSON),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=NOW,
        ),
        sa.CheckConstraint(
            "level IN ('debug', 'info', 'warning', 'error')",
            name="ck_execution_logs_level",
        ),
    )
    op.create_index(
        "idx_execution_logs_job_time", "execution_logs", ["job_id", "recorded_at"]
    )


def downgrade() -> None:
    for table in (
        "execution_logs",
        "background_jobs",
        "document_chunks",
        "source_documents",
        "knowledge_bases",
        "courses",
        "users",
    ):
        op.drop_table(table)
