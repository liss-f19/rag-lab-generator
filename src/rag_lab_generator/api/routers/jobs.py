"""Job status and execution logs (NFR-14)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from rag_lab_generator.api.deps import ContainerDep, CurrentUser
from rag_lab_generator.api.schemas import ExecutionLogOut, JobOut
from rag_lab_generator.container import Container
from rag_lab_generator.domain.errors import NotFoundError
from rag_lab_generator.domain.models import Job, User, UserRole

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _visible_job(container: Container, job_id: UUID, user: User) -> Job:
    job = container.job_service.get(job_id)
    if job.requested_by != user.user_id and user.role is not UserRole.ADMINISTRATOR:
        # Same answer as for a missing job, so job ids of other users are not revealed.
        raise NotFoundError("Job not found.", details={"job_id": str(job_id)})
    return job


@router.get("/{job_id}", response_model=JobOut, summary="Job status and result")
def get_job(job_id: UUID, container: ContainerDep, user: CurrentUser) -> JobOut:
    return JobOut.from_domain(_visible_job(container, job_id, user))


@router.get(
    "/{job_id}/logs", response_model=list[ExecutionLogOut], summary="Job execution log"
)
def get_job_logs(
    job_id: UUID, container: ContainerDep, user: CurrentUser
) -> list[ExecutionLogOut]:
    _visible_job(container, job_id, user)
    return [
        ExecutionLogOut(
            level=log.level,
            event_type=log.event_type,
            message=log.message,
            details=log.details,
        )
        for log in container.jobs.list_logs(job_id)
    ]
