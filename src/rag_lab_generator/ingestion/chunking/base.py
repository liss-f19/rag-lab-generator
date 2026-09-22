"""
Role:   Abstract base for chunking strategies.
Input:  Settings (chunk_size, chunk_overlap_ratio); a Document or LabDocument at chunk time.
Output: Ordered list of Chunk with ids "<strategy>:<document_id>:<idx>".
Flow:   Subclasses implement chunk(); base provides make_chunk() that fills ids and provenance.
"""

from abc import ABC, abstractmethod
from typing import Any

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, ChunkKind, Document


class Chunker(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chunk_size = settings.chunk_size
        self.overlap = int(settings.chunk_size * settings.chunk_overlap_ratio)

    @abstractmethod
    def chunk(self, doc: Document) -> list[Chunk]:
        """Split one document into chunks; idx must be contiguous from 0."""

    def make_chunk(
        self,
        doc: Document,
        idx: int,
        text: str,
        kind: ChunkKind,
        section_id: str | None = None,
        parent_id: str | None = None,
        **metadata: Any,
    ) -> Chunk:
        return Chunk(
            id=f"{self.name}:{doc.id}:{idx}",
            document_id=doc.id,
            course=doc.course,
            lab_id=doc.lab_id or (doc.id if doc.kind == "lab" else None),
            kind=kind,
            strategy=self.name,
            idx=idx,
            text=text,
            section_id=section_id,
            parent_id=parent_id,
            metadata=metadata,
        )
