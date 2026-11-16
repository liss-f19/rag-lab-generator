"""PostgreSQL implementations of the repository ports.

Each method runs in its own transaction; replace_chunks swaps all fragments of a
document atomically.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from rag_lab_generator.domain.errors import NotFoundError
from rag_lab_generator.domain.models import (
    Chunk,
    DocumentFilter,
    IngestionStatus,
    Job,
    JobStatus,
    JobType,
    KnowledgeBaseRole,
    SourceDocument,
    User,
    UserRole,
)
from rag_lab_generator.domain.ports import ExecutionLog
from rag_lab_generator.infrastructure.orm import (
    BackgroundJobRow,
    CourseRow,
    DocumentChunkRow,
    ExecutionLogRow,
    KnowledgeBaseRow,
    SourceDocumentRow,
    UserRow,
    utc_now,
)


class SqlUserRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def add_user(self, user: User) -> None:
        with self._sessions.begin() as session:
            session.add(
                UserRow(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                    user_role=str(user.role),
                )
            )

    def get_user(self, user_id: UUID) -> User | None:
        with self._sessions() as session:
            row = session.get(UserRow, user_id)
            return _user(row) if row else None

    def get_user_by_email(self, email: str) -> User | None:
        with self._sessions() as session:
            row = session.scalars(select(UserRow).where(UserRow.email == email)).first()
            return _user(row) if row else None


def _user(row: UserRow) -> User:
    return User(
        user_id=row.user_id,
        email=row.email,
        display_name=row.display_name,
        role=UserRole(row.user_role),
    )


_CHUNK_COUNT = (
    select(
        func.count(  # pylint: disable=not-callable
            DocumentChunkRow.chunk_id
        )
    )
    .where(DocumentChunkRow.document_id == SourceDocumentRow.document_id)
    .correlate(SourceDocumentRow)
    .scalar_subquery()
)


class SqlDocumentRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def add_document(self, document: SourceDocument) -> None:
        with self._sessions.begin() as session:
            knowledge_base_id = _ensure_knowledge_base(
                session, document.course_id, document.knowledge_base
            )
            session.add(
                SourceDocumentRow(
                    document_id=document.document_id,
                    knowledge_base_id=knowledge_base_id,
                    uploaded_by=document.uploaded_by,
                    filename=document.filename,
                    media_type=document.media_type,
                    storage_uri=document.storage_uri,
                    checksum_sha256=document.checksum_sha256,
                    doc_metadata=dict(document.metadata),
                    ingestion_status=str(document.ingestion_status),
                    error_message=document.error_message,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )
            )

    def get_document(self, document_id: UUID) -> SourceDocument:
        with self._sessions() as session:
            row = session.execute(
                _document_select().where(SourceDocumentRow.document_id == document_id)
            ).first()
            if row is None:
                raise NotFoundError(
                    "Document not found.", details={"document_id": str(document_id)}
                )
            return _document(*row)

    def list_documents(
        self, doc_filter: DocumentFilter, limit: int, offset: int
    ) -> tuple[list[SourceDocument], int]:
        conditions = _filter_conditions(doc_filter)
        with self._sessions() as session:
            total = session.scalar(
                select(
                    func.count(  # pylint: disable=not-callable
                    )
                )
                .select_from(SourceDocumentRow)
                .join(KnowledgeBaseRow)
                .where(*conditions)
            )
            rows = session.execute(
                _document_select()
                .where(*conditions)
                .order_by(SourceDocumentRow.created_at, SourceDocumentRow.document_id)
                .limit(limit)
                .offset(offset)
            ).all()
            return [_document(*row) for row in rows], int(total or 0)

    def update_metadata(
        self, document_id: UUID, fields: dict[str, Any]
    ) -> SourceDocument:
        with self._sessions.begin() as session:
            row = session.get(SourceDocumentRow, document_id)
            if row is None:
                raise NotFoundError(
                    "Document not found.", details={"document_id": str(document_id)}
                )
            row.doc_metadata = {**row.doc_metadata, **fields}
            row.updated_at = utc_now()
        return self.get_document(document_id)

    def set_ingestion_status(
        self,
        document_id: UUID,
        status: IngestionStatus,
        error_message: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            row = session.get(SourceDocumentRow, document_id)
            if row is None:
                raise NotFoundError(
                    "Document not found.", details={"document_id": str(document_id)}
                )
            row.ingestion_status = str(status)
            row.error_message = error_message
            row.updated_at = utc_now()

    def replace_chunks(self, document_id: UUID, chunks: Sequence[Chunk]) -> None:
        with self._sessions.begin() as session:
            session.execute(
                delete(DocumentChunkRow).where(
                    DocumentChunkRow.document_id == document_id
                )
            )
            session.add_all(
                DocumentChunkRow(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_path=list(chunk.section_path),
                    chunk_metadata={"characters": len(chunk.content)},
                    chroma_collection=chunk.chroma_collection,
                    chroma_record_id=chunk.chroma_record_id,
                )
                for chunk in chunks
            )

    def list_chunks(self, document_id: UUID) -> list[Chunk]:
        with self._sessions() as session:
            rows = session.scalars(
                select(DocumentChunkRow)
                .where(DocumentChunkRow.document_id == document_id)
                .order_by(DocumentChunkRow.chunk_index)
            ).all()
            return [_chunk(row) for row in rows]

    def get_chunks(self, chunk_ids: Sequence[UUID]) -> dict[UUID, Chunk]:
        if not chunk_ids:
            return {}
        with self._sessions() as session:
            rows = session.scalars(
                select(DocumentChunkRow).where(
                    DocumentChunkRow.chunk_id.in_(list(chunk_ids))
                )
            ).all()
            return {row.chunk_id: _chunk(row) for row in rows}


def _ensure_knowledge_base(
    session: Session, course_id: str, role: KnowledgeBaseRole
) -> UUID:
    """Return the knowledge base of a course, creating the course and base if needed."""
    for _ in range(2):
        existing = session.scalars(
            select(KnowledgeBaseRow.knowledge_base_id).where(
                KnowledgeBaseRow.course_id == course_id,
                KnowledgeBaseRow.knowledge_base_role == str(role),
            )
        ).first()
        if existing is not None:
            return existing
        try:
            with session.begin_nested():
                if session.get(CourseRow, course_id) is None:
                    session.add(CourseRow(course_id=course_id, name=course_id))
                    session.flush()
                knowledge_base = KnowledgeBaseRow(
                    knowledge_base_id=uuid4(),
                    course_id=course_id,
                    knowledge_base_role=str(role),
                    name=f"{course_id} ({role})",
                )
                session.add(knowledge_base)
            return knowledge_base.knowledge_base_id
        except IntegrityError:
            continue  # created concurrently by another request; read it again
    raise RuntimeError(f"Could not create knowledge base {course_id}/{role}")


def _document_select() -> Select[Any]:
    return select(
        SourceDocumentRow,
        KnowledgeBaseRow.course_id,
        KnowledgeBaseRow.knowledge_base_role,
        _CHUNK_COUNT,
    ).join(KnowledgeBaseRow)


def _filter_conditions(doc_filter: DocumentFilter) -> list[Any]:
    conditions: list[Any] = []
    if doc_filter.course_id is not None:
        conditions.append(KnowledgeBaseRow.course_id == doc_filter.course_id)
    if doc_filter.knowledge_bases is not None:
        roles = sorted(str(role) for role in doc_filter.knowledge_bases)
        conditions.append(KnowledgeBaseRow.knowledge_base_role.in_(roles))
    if doc_filter.document_type is not None:
        conditions.append(
            SourceDocumentRow.doc_metadata["document_type"].as_string()
            == doc_filter.document_type
        )
    if doc_filter.topic is not None:
        conditions.append(
            SourceDocumentRow.doc_metadata["topic"].as_string() == doc_filter.topic
        )
    if doc_filter.ingestion_status is not None:
        conditions.append(
            SourceDocumentRow.ingestion_status == str(doc_filter.ingestion_status)
        )
    return conditions


def _document(
    row: SourceDocumentRow, course_id: str, knowledge_base_role: str, chunk_count: int
) -> SourceDocument:
    return SourceDocument(
        document_id=row.document_id,
        course_id=course_id,
        knowledge_base=KnowledgeBaseRole(knowledge_base_role),
        filename=row.filename,
        media_type=row.media_type,
        storage_uri=row.storage_uri,
        checksum_sha256=row.checksum_sha256 or "",
        metadata=dict(row.doc_metadata or {}),
        ingestion_status=IngestionStatus(row.ingestion_status),
        uploaded_by=row.uploaded_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        error_message=row.error_message,
        chunk_count=int(chunk_count or 0),
    )


def _chunk(row: DocumentChunkRow) -> Chunk:
    return Chunk(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        chunk_index=row.chunk_index,
        content=row.content,
        section_path=tuple(row.section_path or ()),
        page_number=row.page_number,
        chroma_collection=row.chroma_collection,
        chroma_record_id=row.chroma_record_id,
    )


class SqlJobRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def add_job(self, job: Job) -> None:
        with self._sessions.begin() as session:
            session.add(
                BackgroundJobRow(
                    job_id=job.job_id,
                    rq_job_id=str(job.job_id),
                    job_type=str(job.job_type),
                    status=str(job.status),
                    requested_by=job.requested_by,
                    course_id=job.course_id,
                    document_id=job.document_id,
                    parameters=dict(job.parameters),
                    request_id=job.request_id,
                    created_at=job.created_at,
                )
            )

    def get_job(self, job_id: UUID) -> Job:
        with self._sessions() as session:
            return _job(self._row(session, job_id))

    def mark_running(self, job_id: UUID) -> Job:
        return self._update(job_id, status=str(JobStatus.RUNNING), started_at=utc_now())

    def mark_succeeded(self, job_id: UUID, result: dict[str, Any]) -> Job:
        return self._update(
            job_id,
            status=str(JobStatus.SUCCEEDED),
            result=result,
            completed_at=utc_now(),
        )

    def mark_failed(self, job_id: UUID, error_code: str, error_message: str) -> Job:
        return self._update(
            job_id,
            status=str(JobStatus.FAILED),
            error_code=error_code,
            error_message=error_message,
            completed_at=utc_now(),
        )

    def add_log(
        self,
        job_id: UUID,
        level: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                ExecutionLogRow(
                    job_id=job_id,
                    level=level,
                    event_type=event_type,
                    message=message,
                    details=details or {},
                )
            )

    def list_logs(self, job_id: UUID) -> list[ExecutionLog]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ExecutionLogRow)
                .where(ExecutionLogRow.job_id == job_id)
                .order_by(ExecutionLogRow.log_id)
            ).all()
            return [
                ExecutionLog(
                    row.level, row.event_type, row.message, dict(row.details or {})
                )
                for row in rows
            ]

    def _update(self, job_id: UUID, **values: Any) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            for name, value in values.items():
                setattr(row, name, value)
            session.flush()
            return _job(row)

    @staticmethod
    def _row(session: Session, job_id: UUID) -> BackgroundJobRow:
        row = session.get(BackgroundJobRow, job_id)
        if row is None:
            raise NotFoundError("Job not found.", details={"job_id": str(job_id)})
        return row


def _job(row: BackgroundJobRow) -> Job:
    return Job(
        job_id=row.job_id,
        job_type=JobType(row.job_type),
        status=JobStatus(row.status),
        requested_by=row.requested_by,
        created_at=row.created_at,
        course_id=row.course_id,
        document_id=row.document_id,
        parameters=dict(row.parameters or {}),
        result=dict(row.result) if row.result is not None else None,
        error_code=row.error_code,
        error_message=row.error_message,
        request_id=row.request_id,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )
