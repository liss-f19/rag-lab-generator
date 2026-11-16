"""Uniform error envelope and request identifiers (Stage 2, Section 8.4)."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from rag_lab_generator.application.jobs import QueueUnavailableError
from rag_lab_generator.domain.errors import (
    DocumentTooLargeError,
    DomainError,
    EmbeddingError,
    ExtractionError,
    InvalidRequestError,
    NotFoundError,
    UnsupportedDocumentFormatError,
)

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_DOMAIN_STATUS: list[tuple[type[DomainError], int]] = [
    (NotFoundError, 404),
    (UnsupportedDocumentFormatError, 415),
    (DocumentTooLargeError, 413),
    (ExtractionError, 422),
    (InvalidRequestError, 422),
    (QueueUnavailableError, 503),
    (EmbeddingError, 502),
]

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_FAILED",
}


class ApiError(Exception):
    def __init__(  # pylint: disable=too-many-arguments
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", None) or "unknown"


def error_response(request: Request, error: ApiError) -> JSONResponse:
    request_id = request_id_of(request)
    body = {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "request_id": request_id,
        }
    }
    return JSONResponse(
        status_code=error.status_code,
        content=jsonable_encoder(body),
        headers={**(error.headers or {}), REQUEST_ID_HEADER: request_id},
    )


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def assign_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request.state.request_id = (
            incoming if _VALID_REQUEST_ID.match(incoming) else f"req_{uuid4().hex[:16]}"
        )
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code = next(
            (status for kind, status in _DOMAIN_STATUS if isinstance(exc, kind)), 400
        )
        return error_response(
            request, ApiError(status_code, exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"location": list(error.get("loc", ())), "message": error.get("msg", "")}
            for error in exc.errors()
        ]
        return error_response(
            request,
            ApiError(
                422, "VALIDATION_FAILED", "The request is invalid.", {"errors": errors}
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return error_response(
            request,
            ApiError(
                exc.status_code,
                _HTTP_CODES.get(exc.status_code, "HTTP_ERROR"),
                str(exc.detail),
                headers=dict(exc.headers or {}),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error in request %s", request_id_of(request), exc_info=exc
        )
        return error_response(
            request, ApiError(500, "INTERNAL_ERROR", "An internal error occurred.")
        )
