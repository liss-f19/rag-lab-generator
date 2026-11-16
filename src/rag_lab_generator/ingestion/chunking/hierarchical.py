"""
Role:   Default chunker: keeps the document outline by emitting one chunk per section.
Input:  Document / LabDocument; Settings (chunk_size) through Chunker.
Output: List of Chunk carrying section_id, parent_id and a breadcrumb in text and metadata.
Flow:   Walks sections in order, prepends "Lab title > Section title" to the body and links each
        chunk to the chunk of its parent section; sections above chunk_size are split with the
        semantic splitter and the extra pieces hang under the first one. Lab tasks become TASK
        chunks (plus per-stage-group children when oversized) and source files CODE chunks.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.chunking.base import Chunker
from rag_lab_generator.ingestion.chunking.fixed import document_chunk_kind, lab_code_chunks
from rag_lab_generator.ingestion.chunking.semantic import SemanticChunker
from rag_lab_generator.models import Chunk, ChunkKind, Document, LabDocument, Section, Stage
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder

SECTION_OVERLAP_RATIO = 0.1


@register("chunker", "hierarchical")
class HierarchicalChunker(Chunker):
    name = "hierarchical"

    def __init__(self, settings: Settings, embedder: Embedder | None = None) -> None:
        super().__init__(settings)
        self._embedder = embedder
        self._splitter: SemanticChunker | None = None

    def chunk(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        by_id = {section.id: section for section in doc.sections}
        chunk_of_section: dict[str, str] = {}
        kind = document_chunk_kind(doc.kind)
        for section in sorted(doc.sections, key=lambda s: s.order):
            body = section.text.strip()
            if not body:
                continue
            breadcrumb = self._breadcrumb(doc, section, by_id)
            parent = chunk_of_section.get(section.parent_id or "")
            pieces = self._section_pieces(body)
            for part, piece in enumerate(pieces):
                chunk = self.make_chunk(
                    doc,
                    len(chunks),
                    f"{breadcrumb}\n\n{piece}",
                    kind,
                    section_id=section.id,
                    parent_id=parent if part == 0 else chunk_of_section[section.id],
                    title=section.title,
                    level=section.level,
                    breadcrumb=breadcrumb,
                    part=part,
                    n_parts=len(pieces),
                )
                chunks.append(chunk)
                if part == 0:
                    chunk_of_section[section.id] = chunk.id
        if isinstance(doc, LabDocument):
            chunks.extend(self._task_chunks(doc, len(chunks)))
            chunks.extend(lab_code_chunks(self, doc, len(chunks)))
        return chunks

    def _section_pieces(self, body: str) -> list[str]:
        """Keep a section whole, or split it semantically when it exceeds the chunk size."""
        if len(body) <= self.chunk_size:
            return [body]
        pieces = self._semantic_splitter().split_text(body, overlap_ratio=SECTION_OVERLAP_RATIO)
        return pieces or [body]

    def _semantic_splitter(self) -> SemanticChunker:
        if self._splitter is None:
            self._splitter = SemanticChunker(self.settings, embedder=self._embedder)
        return self._splitter

    def _task_chunks(self, doc: LabDocument, start_idx: int) -> list[Chunk]:
        """Emit one chunk per task and, for oversized tasks, one chunk per stage group."""
        chunks: list[Chunk] = []
        idx = start_idx
        for task in doc.tasks:
            head = "\n\n".join(p.strip() for p in (task.title, task.statement) if p.strip())
            stage_texts = [f"Stage {stage.n}: {stage.text.strip()}" for stage in task.stages]
            full = "\n\n".join([head, *stage_texts, task.notes.strip()]).strip()
            if not full:
                continue
            task_chunk = self.make_chunk(
                doc,
                idx,
                full,
                ChunkKind.TASK,
                section_id=f"task:{task.id}",
                task_id=task.id,
                title=task.title,
                n_stages=len(task.stages),
            )
            chunks.append(task_chunk)
            idx += 1
            if len(full) <= self.chunk_size:
                continue
            for group in self._stage_groups(task.stages, len(head)):
                text = "\n\n".join([head, *(f"Stage {s.n}: {s.text.strip()}" for s in group)])
                chunks.append(
                    self.make_chunk(
                        doc,
                        idx,
                        text,
                        ChunkKind.TASK,
                        section_id=f"task:{task.id}",
                        parent_id=task_chunk.id,
                        task_id=task.id,
                        title=task.title,
                        stages=[s.n for s in group],
                    )
                )
                idx += 1
        return chunks

    def _stage_groups(self, stages: list[Stage], head_size: int) -> list[list[Stage]]:
        """Pack consecutive stages into groups that stay below the chunk size."""
        groups: list[list[Stage]] = []
        current: list[Stage] = []
        size = head_size
        for stage in stages:
            length = len(stage.text) + 16
            if current and size + length > self.chunk_size:
                groups.append(current)
                current, size = [], head_size
            current.append(stage)
            size += length
        if current:
            groups.append(current)
        return groups

    @staticmethod
    def _breadcrumb(doc: Document, section: Section, by_id: dict[str, Section]) -> str:
        """Build "Document title > ... > Section title" following parent links upwards."""
        titles = [section.title]
        seen = {section.id}
        parent_id = section.parent_id
        while parent_id and parent_id in by_id and parent_id not in seen:
            seen.add(parent_id)
            parent = by_id[parent_id]
            titles.append(parent.title)
            parent_id = parent.parent_id
        titles.append(doc.title)
        return " > ".join(reversed(titles))
