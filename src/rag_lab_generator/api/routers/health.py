"""Service health and readiness."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from rag_lab_generator import __version__
from rag_lab_generator.api.deps import ContainerDep
from rag_lab_generator.api.schemas import HealthOut
from rag_lab_generator.infrastructure.db import ping

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="Service health and readiness")
def health(container: ContainerDep, response: Response) -> HealthOut:
    checks: dict[str, str] = {}
    try:
        ping(container.engine)
        checks["database"] = "ok"
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Database health check failed", exc_info=True)
        checks["database"] = "unavailable"
    try:
        container.queue.ping()
        checks["queue"] = "ok"
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Queue health check failed", exc_info=True)
        checks["queue"] = "unavailable"
    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(
        status="ok" if healthy else "degraded", version=__version__, checks=checks
    )
