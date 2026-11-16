"""Course-material use cases on the API side (FR-01 to FR-06)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from rag_lab_generator.application.jobs import JobService
from rag_lab_generator.domain.errors import (
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidRequestError,
    NotFoundError,
)
from rag_lab_generator.domain.models import (
    DocumentFilter,
    DocumentMetadata,
    IngestionStatus,
    Job,
    JobType,
    SourceDocument,
    User,
)
from rag_lab_generator.domain.ports import DocumentRepository, FileStorage
from rag_lab_generator.ingestion.extractors import check_signature, media_type_for

EDITABLE_METADATA_FIELDS = frozenset(
    {
        "document_type",
        "topic",
        "version",
        "learning_outcomes",
        "difficulty",
        "authority_level",
    }
)


class DocumentService:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        files: FileStorage,
        jobs: JobService,
        max_upload_bytes: int,
    ) -> None:
        self._documents = documents
        self._files = files
        self._jobs = jobs
        self._max_upload_bytes = max_upload_bytes

    def upload(  # pylint: disable=too-many-arguments
        self,
        *,
        filename: str,
        data: bytes,
        metadata: DocumentMetadata,
        user: User,
        request_id: str | None = None,
    ) -> tuple[SourceDocument, Job]:
        """Store the file, register the document, and queue its ingestion."""
        if len(data) > self._max_upload_bytes:
            raise DocumentTooLargeError(
                "The uploaded file exceeds the size limit.",
                details={"max_bytes": self._max_upload_bytes},
            )
        if not data:
            raise EmptyDocumentError("The uploaded file is empty.")
        safe_name = PurePath(filename.replace("\\", "/")).name[:512] or "document"
        media_type = media_type_for(safe_name)
        check_signature(media_type, data)

        uri = self._files.save(data, PurePath(safe_name).suffix.lower())
        now = datetime.now(UTC)
        document = SourceDocument(
            document_id=uuid4(),
            course_id=metadata.course_id,
            knowledge_base=metadata.knowledge_base,
            filename=safe_name,
            media_type=media_type,
            storage_uri=uri,
            checksum_sha256=hashlib.sha256(data).hexdigest(),
            metadata=metadata.descriptive_fields(),
            ingestion_status=IngestionStatus.QUEUED,
            uploaded_by=user.user_id,
            created_at=now,
            updated_at=now,
        )
        try:
            self._documents.add_document(document)
        except Exception:
            self._files.delete(uri)
            raise
        job = self._jobs.submit(
            JobType.DOCUMENT_INGESTION,
            user,
            document_id=document.document_id,
            request_id=request_id,
        )
        return self._documents.get_document(document.document_id), job

    def get(self, document_id: UUID) -> SourceDocument:
        return self._documents.get_document(document_id)

    def list(
        self, doc_filter: DocumentFilter, limit: int, offset: int
    ) -> tuple[list[SourceDocument], int]:
        return self._documents.list_documents(doc_filter, limit, offset)

    def update_metadata(
        self, document_id: UUID, fields: dict[str, Any]
    ) -> SourceDocument:
        unknown = set(fields) - EDITABLE_METADATA_FIELDS
        if unknown:
            raise InvalidRequestError(
                "These fields cannot be edited.", details={"fields": sorted(unknown)}
            )
        return self._documents.update_metadata(document_id, fields)

    def index_course(
        self, course_id: str, user: User, request_id: str | None = None
    ) -> Job:
        self._require_course_documents(course_id)
        return self._jobs.submit(
            JobType.COURSE_INDEXING, user, course_id=course_id, request_id=request_id
        )

    def submit_retrieval(
        self,
        course_id: str,
        parameters: dict[str, Any],
        user: User,
        request_id: str | None = None,
    ) -> Job:
        self._require_course_documents(course_id)
        return self._jobs.submit(
            JobType.RETRIEVAL,
            user,
            course_id=course_id,
            parameters=parameters,
            request_id=request_id,
        )

    def _require_course_documents(self, course_id: str) -> None:
        _, total = self._documents.list_documents(
            DocumentFilter(course_id=course_id), limit=1, offset=0
        )
        if total == 0:
            raise NotFoundError(
                f"Course {course_id} has no documents.",
                details={"course_id": course_id},
            )
