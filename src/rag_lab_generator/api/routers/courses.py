"""Course-level jobs: indexing and retrieval preview."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request, status

from rag_lab_generator.api.deps import ContainerDep, CourseMaintainer, RetrievalUser
from rag_lab_generator.api.errors import request_id_of
from rag_lab_generator.api.schemas import (
    COURSE_ID_PATTERN,
    JobAccepted,
    RetrievalRequest,
)

router = APIRouter(prefix="/courses", tags=["courses"])

CourseId = Annotated[str, Path(pattern=COURSE_ID_PATTERN)]


@router.post(
    "/{course_id}/index",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAccepted,
    summary="Re-index all documents of a course",
)
def index_course(
    course_id: CourseId,
    request: Request,
    container: ContainerDep,
    user: CourseMaintainer,
) -> JobAccepted:
    job = container.document_service.index_course(
        course_id, user, request_id_of(request)
    )
    return JobAccepted.from_domain(job)


@router.post(
    "/{course_id}/retrieval",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAccepted,
    summary="Retrieve ranked evidence from the course knowledge bases",
)
def retrieve(
    course_id: CourseId,
    body: RetrievalRequest,
    request: Request,
    container: ContainerDep,
    user: RetrievalUser,
) -> JobAccepted:
    job = container.document_service.submit_retrieval(
        course_id, body.model_dump(mode="json"), user, request_id_of(request)
    )
    return JobAccepted.from_domain(job)
