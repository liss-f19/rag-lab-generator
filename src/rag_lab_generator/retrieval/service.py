"""Retrieval use case executed by the worker for retrieval jobs."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from rag_lab_generator.domain.models import RetrievalQuery
from rag_lab_generator.domain.policy import EvidencePurpose, SourceAuthorityPolicy
from rag_lab_generator.domain.ports import RetrievalStrategy


class RetrievalService:
    def __init__(self, strategy: RetrievalStrategy, embedding_model: str) -> None:
        self._strategy = strategy
        self._embedding_model = embedding_model

    def run(self, course_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        purpose = EvidencePurpose(parameters.get("purpose", EvidencePurpose.CONTEXT))
        top_k = int(parameters.get("top_k", 5))
        query = RetrievalQuery(
            course_id=course_id,
            text=str(parameters["query"]),
            document_type=parameters.get("document_type"),
            topic=parameters.get("topic"),
        )
        started = perf_counter()
        evidence = self._strategy.retrieve(
            query, SourceAuthorityPolicy.for_purpose(purpose), top_k
        )
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "strategy": self._strategy.name,
            "embedding_model": self._embedding_model,
            "purpose": str(purpose),
            "top_k": top_k,
            "latency_ms": latency_ms,
            "evidence": [
                {
                    "chunk_id": str(candidate.chunk_id),
                    "document_id": str(candidate.document_id),
                    "filename": candidate.filename,
                    "knowledge_base": str(candidate.knowledge_base),
                    "section_path": list(candidate.section_path),
                    "page_number": candidate.page_number,
                    "similarity": candidate.similarity,
                    "score": candidate.score,
                    "excerpt": candidate.excerpt,
                }
                for candidate in evidence
            ],
        }
