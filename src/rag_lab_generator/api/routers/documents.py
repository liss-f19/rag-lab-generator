"""Course materials: upload, listing, inspection, and metadata (FR-01 to FR-05)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from rag_lab_generator.api.deps import ContainerDep, CourseMaintainer
from rag_lab_generator.api.errors import ApiError, request_id_of
from rag_lab_generator.api.schemas import (
    DocumentListQuery,
    DocumentMetadataIn,
    DocumentMetadataPatch,
    DocumentOut,
    DocumentPage,
    DocumentUploadAccepted,
    job_status_url,
)
from rag_lab_generator.domain.errors import DocumentTooLargeError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadAccepted,
    summary="Upload a PDF, HTML, TXT, or Markdown source and queue its ingestion",
)
async def upload_document(
    request: Request,
    container: ContainerDep,
    user: CourseMaintainer,
    file: Annotated[UploadFile, File(description="Source document")],
    metadata: Annotated[str, Form(description="JSON document metadata")],
) -> DocumentUploadAccepted:
    try:
        parsed = DocumentMetadataIn.model_validate_json(metadata)
    except ValidationError as exc:
        errors = [
            {"location": ["metadata", *error["loc"]], "message": error["msg"]}
            for error in exc.errors()
        ]
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "The document metadata is invalid.",
            {"errors": errors},
        ) from None
    limit = container.settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise DocumentTooLargeError(
            "The uploaded file exceeds the size limit.", details={"max_bytes": limit}
        )
    document, job = await run_in_threadpool(
        container.document_service.upload,
        filename=file.filename or "document",
        data=data,
        metadata=parsed.to_domain(),
        user=user,
        request_id=request_id_of(request),
    )
    return DocumentUploadAccepted(
        document_id=document.document_id,
        ingestion_status=document.ingestion_status,
        job_id=job.job_id,
        status_url=job_status_url(job.job_id),
    )


@router.get("", response_model=DocumentPage, summary="List documents with filters")
def list_documents(
    query: Annotated[DocumentListQuery, Query()],
    container: ContainerDep,
    _user: CourseMaintainer,
) -> DocumentPage:
    documents, total = container.document_service.list(
        query.to_filter(), query.limit, query.offset
    )
    return DocumentPage(
        items=[DocumentOut.from_domain(document) for document in documents],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get(
    "/{document_id}", response_model=DocumentOut, summary="Inspect one document"
)
def get_document(
    document_id: UUID, container: ContainerDep, _user: CourseMaintainer
) -> DocumentOut:
    return DocumentOut.from_domain(container.document_service.get(document_id))


@router.patch(
    "/{document_id}/metadata",
    response_model=DocumentOut,
    summary="Update document metadata without changing the source file",
)
def update_metadata(
    document_id: UUID,
    patch: DocumentMetadataPatch,
    container: ContainerDep,
    _user: CourseMaintainer,
) -> DocumentOut:
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise ApiError(422, "VALIDATION_FAILED", "No metadata fields to update.")
    return DocumentOut.from_domain(
        container.document_service.update_metadata(document_id, fields)
    )
