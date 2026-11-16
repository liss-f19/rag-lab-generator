"""Ingestion and indexing use cases; they run in the worker process."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from rag_lab_generator.domain.errors import DomainError, EmptyDocumentError
from rag_lab_generator.domain.models import (
    Chunk,
    DocumentFilter,
    IngestionStatus,
    vector_collection_name,
)
from rag_lab_generator.domain.ports import (
    DocumentRepository,
    EmbeddingClient,
    FileStorage,
    VectorIndex,
)
from rag_lab_generator.ingestion.chunking import StructuredChunker
from rag_lab_generator.ingestion.extractors import extractor_for

logger = logging.getLogger(__name__)


@contextmanager
def _timed(timings: dict[str, float], key: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings[key] = round((perf_counter() - started) * 1000, 2)


class IngestionService:
    """Extract -> chunk -> embed -> persist fragments -> write vectors."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        documents: DocumentRepository,
        files: FileStorage,
        chunker: StructuredChunker,
        embedder: EmbeddingClient,
        index: VectorIndex,
    ) -> None:
        self._documents = documents
        self._files = files
        self._chunker = chunker
        self._embedder = embedder
        self._index = index

    def ingest(self, document_id: UUID) -> dict[str, Any]:
        document = self._documents.get_document(document_id)
        self._documents.set_ingestion_status(document_id, IngestionStatus.PROCESSING)
        timings: dict[str, float] = {}
        try:
            with _timed(timings, "extract_ms"):
                data = self._files.read(document.storage_uri)
                blocks = extractor_for(document.media_type).extract(data)
            if not blocks:
                raise EmptyDocumentError(
                    "No text could be extracted from the document."
                )
            with _timed(timings, "chunk_ms"):
                pieces = self._chunker.split(blocks)
            collection = vector_collection_name(
                document.course_id, self._embedder.model_id
            )
            chunks = []
            for position, piece in enumerate(pieces):
                chunk_id = uuid4()
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=position,
                        content=piece.content,
                        section_path=piece.section_path,
                        page_number=piece.page_number,
                        chroma_collection=collection,
                        chroma_record_id=str(chunk_id),
                    )
                )
            with _timed(timings, "embed_ms"):
                batch = self._embedder.embed(
                    [chunk.embedding_text() for chunk in chunks]
                )
            with _timed(timings, "persist_ms"):
                self._documents.replace_chunks(document_id, chunks)
            with _timed(timings, "index_ms"):
                self._index.delete_document(collection, document_id)
                self._index.upsert(
                    collection,
                    [chunk.chroma_record_id for chunk in chunks],
                    batch.vectors,
                    [
                        {
                            "document_id": str(document_id),
                            "chunk_id": str(chunk.chunk_id),
                            "course_id": document.course_id,
                            "knowledge_base": str(document.knowledge_base),
                        }
                        for chunk in chunks
                    ],
                )
        except DomainError as exc:
            self._documents.set_ingestion_status(
                document_id, IngestionStatus.FAILED, exc.message
            )
            raise
        except Exception:
            self._documents.set_ingestion_status(
                document_id, IngestionStatus.FAILED, "Internal error during ingestion."
            )
            raise
        self._documents.set_ingestion_status(document_id, IngestionStatus.INDEXED)
        logger.info("Indexed document %s: %d fragments", document_id, len(chunks))
        return {
            "document_id": str(document_id),
            "chunk_count": len(chunks),
            "character_count": sum(len(chunk.content) for chunk in chunks),
            "collection": collection,
            "embedding_model": self._embedder.model_id,
            "embedding_tokens": batch.token_count,
            "timings_ms": timings,
        }

    def index_course(self, course_id: str) -> dict[str, Any]:
        """Re-index every document of a course; one failure does not stop the rest."""
        documents, _ = self._documents.list_documents(
            DocumentFilter(course_id=course_id), limit=100_000, offset=0
        )
        indexed: list[str] = []
        failed: list[dict[str, str]] = []
        chunk_count = 0
        for document in documents:
            try:
                result = self.ingest(document.document_id)
            except DomainError as exc:
                failed.append(
                    {"document_id": str(document.document_id), "error": exc.message}
                )
                continue
            indexed.append(str(document.document_id))
            chunk_count += result["chunk_count"]
        return {
            "course_id": course_id,
            "documents": len(documents),
            "indexed": len(indexed),
            "failed": failed,
            "chunk_count": chunk_count,
            "embedding_model": self._embedder.model_id,
        }
