"""Chroma adapter for the VectorIndex port (embedded PersistentClient).

Only the worker process opens the persistent store: Chroma's local storage is
not safe for concurrent writers in several processes (Stage 2, Section 6.1).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError as ChromaNotFoundError

from rag_lab_generator.domain.ports import VectorHit

_UPSERT_BATCH = 1000


class ChromaVectorIndex:
    def __init__(self, persist_directory: Path) -> None:
        persist_directory.mkdir(parents=True, exist_ok=True)
        self._client: ClientAPI = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _collection(self, name: str) -> Collection:
        # Embeddings are always supplied by the application, so no embedding
        # function is attached; cosine distance matches the normalised vectors.
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def upsert(
        self,
        collection: str,
        record_ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, str | int | float | bool]],
    ) -> None:
        if not record_ids:
            return
        target = self._collection(collection)
        for start in range(0, len(record_ids), _UPSERT_BATCH):
            end = start + _UPSERT_BATCH
            target.upsert(
                ids=list(record_ids[start:end]),
                embeddings=[list(vector) for vector in embeddings[start:end]],
                metadatas=[dict(metadata) for metadata in metadatas[start:end]],
            )

    def delete_document(self, collection: str, document_id: UUID) -> None:
        try:
            target = self._client.get_collection(collection, embedding_function=None)
        except (ChromaNotFoundError, ValueError):
            return
        target.delete(where={"document_id": str(document_id)})

    def query(
        self,
        collection: str,
        embedding: Sequence[float],
        top_k: int,
        document_ids: Sequence[UUID],
    ) -> list[VectorHit]:
        if not document_ids or top_k <= 0:
            return []
        try:
            target = self._client.get_collection(collection, embedding_function=None)
        except (ChromaNotFoundError, ValueError):
            return []
        ids = [str(document_id) for document_id in document_ids]
        where = (
            {"document_id": ids[0]} if len(ids) == 1 else {"document_id": {"$in": ids}}
        )
        result = target.query(
            query_embeddings=[list(embedding)],
            n_results=top_k,
            where=where,  # type: ignore[arg-type]
            include=["distances"],
        )
        record_ids = result["ids"][0]
        distances = (result.get("distances") or [[]])[0]
        return [
            VectorHit(record_id=record_id, distance=float(distance))
            for record_id, distance in zip(record_ids, distances, strict=True)
        ]

    def count(self, collection: str) -> int:
        try:
            return self._client.get_collection(
                collection, embedding_function=None
            ).count()
        except (ChromaNotFoundError, ValueError):
            return 0
