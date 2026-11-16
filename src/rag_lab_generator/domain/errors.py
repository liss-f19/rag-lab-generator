"""Domain errors carry a stable machine-readable code (see the API error envelope)."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class UnsupportedDocumentFormatError(DomainError):
    code = "UNSUPPORTED_DOCUMENT_FORMAT"


class DocumentTooLargeError(DomainError):
    code = "DOCUMENT_TOO_LARGE"


class ExtractionError(DomainError):
    """The file has a supported type but its text cannot be extracted (FR-02)."""

    code = "EXTRACTION_FAILED"


class EmptyDocumentError(ExtractionError):
    code = "EMPTY_DOCUMENT"


class EmbeddingError(DomainError):
    code = "EMBEDDING_FAILED"


class InvalidRequestError(DomainError):
    code = "VALIDATION_FAILED"
