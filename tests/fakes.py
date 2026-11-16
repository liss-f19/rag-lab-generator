"""In-memory test doubles for the ports and helpers that build test inputs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from uuid import UUID

from rag_lab_generator.domain.ports import VectorHit


class InMemoryVectorIndex:
    """Exact cosine search over a dict; behaves like the Chroma adapter."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def upsert(  # type: ignore[no-untyped-def]
        self, collection, record_ids, embeddings, metadatas
    ) -> None:
        records = self.collections.setdefault(collection, {})
        for record_id, embedding, metadata in zip(
            record_ids, embeddings, metadatas, strict=True
        ):
            records[record_id] = (list(embedding), dict(metadata))

    def delete_document(self, collection: str, document_id: UUID) -> None:
        records = self.collections.get(collection, {})
        for record_id in [
            key
            for key, (_, meta) in records.items()
            if meta["document_id"] == str(document_id)
        ]:
            del records[record_id]

    def query(
        self,
        collection: str,
        embedding: Sequence[float],
        top_k: int,
        document_ids: Sequence[UUID],
    ) -> list[VectorHit]:
        allowed = {str(document_id) for document_id in document_ids}
        hits = [
            VectorHit(record_id, 1.0 - _cosine(vector, embedding))
            for record_id, (vector, meta) in self.collections.get(
                collection, {}
            ).items()
            if meta["document_id"] in allowed
        ]
        hits.sort(key=lambda hit: hit.distance)
        return hits[:top_k]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


class RecordingQueue:
    """Records enqueued job ids without running them."""

    def __init__(self, fail: bool = False) -> None:
        self.enqueued: list[UUID] = []
        self.fail = fail

    def enqueue(self, job_id: UUID) -> None:
        if self.fail:
            raise ConnectionError("redis is down")
        self.enqueued.append(job_id)

    def ping(self) -> None:
        if self.fail:
            raise ConnectionError("redis is down")


def make_pdf(page_texts: Sequence[str]) -> bytes:
    """Build a minimal valid PDF with one line of Helvetica text per page."""
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    next_id = 4
    for text in page_texts:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
        objects[content_id] = (
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        kids.append(page_id)
    references = " ".join(f"{kid} 0 R" for kid in kids)
    objects[2] = f"<< /Type /Pages /Kids [{references}] /Count {len(kids)} >>".encode()

    output = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref = len(output)
    size = max(objects) + 1
    output += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for number in range(1, size):
        output += f"{offsets[number]:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)
