"""Baseline vector retrieval (dense similarity over the course collection)."""

from __future__ import annotations

from uuid import UUID

from rag_lab_generator.domain.models import (
    DocumentFilter,
    EvidenceCandidate,
    IngestionStatus,
    RetrievalQuery,
    vector_collection_name,
)
from rag_lab_generator.domain.policy import SourceAuthorityPolicy
from rag_lab_generator.domain.ports import (
    DocumentRepository,
    EmbeddingClient,
    VectorIndex,
)


class VectorRetrievalStrategy:
    """Dense retrieval restricted to indexed documents that the policy admits.

    Metadata filters and the knowledge-base policy are resolved in PostgreSQL,
    so the vector store only receives the list of eligible document ids and a
    metadata change never leaves stale filter values in the index. Excerpts are
    read from document_chunks: a vector whose fragment no longer exists is
    dropped instead of being returned as evidence (FR-07, NFR-10).
    """

    name = "vector"

    def __init__(
        self,
        *,
        documents: DocumentRepository,
        embedder: EmbeddingClient,
        index: VectorIndex,
        oversampling: int = 3,
    ) -> None:
        self._documents = documents
        self._embedder = embedder
        self._index = index
        self._oversampling = oversampling

    def retrieve(
        self,
        query: RetrievalQuery,
        policy: SourceAuthorityPolicy,
        top_k: int,
    ) -> list[EvidenceCandidate]:
        eligible, _ = self._documents.list_documents(
            DocumentFilter(
                course_id=query.course_id,
                knowledge_bases=policy.allowed,
                document_type=query.document_type,
                topic=query.topic,
                ingestion_status=IngestionStatus.INDEXED,
            ),
            limit=100_000,
            offset=0,
        )
        if not eligible:
            return []
        documents = {document.document_id: document for document in eligible}
        collection = vector_collection_name(query.course_id, self._embedder.model_id)
        query_vector = self._embedder.embed([query.text]).vectors[0]
        hits = self._index.query(
            collection, query_vector, top_k * self._oversampling, list(documents)
        )
        chunks = self._documents.get_chunks([UUID(hit.record_id) for hit in hits])

        candidates = []
        for hit in hits:
            chunk = chunks.get(UUID(hit.record_id))
            document = documents.get(chunk.document_id) if chunk else None
            if chunk is None or document is None:
                continue
            similarity = 1.0 - hit.distance
            candidates.append(
                EvidenceCandidate(
                    chunk_id=chunk.chunk_id,
                    document_id=document.document_id,
                    filename=document.filename,
                    knowledge_base=document.knowledge_base,
                    excerpt=chunk.content,
                    section_path=chunk.section_path,
                    page_number=chunk.page_number,
                    similarity=round(similarity, 6),
                    score=round(
                        policy.rank_score(similarity, document.knowledge_base), 6
                    ),
                )
            )
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates[:top_k]
