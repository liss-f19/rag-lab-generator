"""
Role:   Baseline chunker: fixed-size sliding window over the document text plus lab extras.
Input:  Document / LabDocument; Settings (chunk_size, chunk_overlap_ratio) through Chunker.
Output: List of Chunk with contiguous idx, kind derived from the document kind.
Flow:   Windows doc.text by chunk_size with overlap, snapping window ends to blank lines that
        lie outside fenced code blocks; then appends one TASK chunk per task and one (or more)
        CODE chunk per source file of a LabDocument. Shared helpers here (document_chunk_kind,
        fenced_spans, split_code, task_text) are reused by the hierarchical and semantic chunkers.
"""

import re

from rag_lab_generator.ingestion.chunking.base import Chunker
from rag_lab_generator.models import Chunk, ChunkKind, Document, DocumentKind, LabDocument, Task
from rag_lab_generator.registry import register

_KIND_MAP: dict[DocumentKind, ChunkKind] = {
    DocumentKind.LAB: ChunkKind.TUTORIAL,
    DocumentKind.LECTURE_PDF: ChunkKind.LECTURE,
    DocumentKind.LECTURE_SLIDES: ChunkKind.LECTURE,
    DocumentKind.LECTURE_INDEX: ChunkKind.LECTURE,
    DocumentKind.LECTURE_CODE: ChunkKind.LECTURE,
    DocumentKind.EXTERNAL_PDF: ChunkKind.LECTURE,
    DocumentKind.COURSE_INFO: ChunkKind.INFO,
    DocumentKind.SUMMARY: ChunkKind.SUMMARY,
}

_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_FENCE = re.compile(r"^[ \t]*(```|~~~)", re.MULTILINE)


def document_chunk_kind(kind: DocumentKind) -> ChunkKind:
    """Map the document kind to the chunk kind used for its prose chunks."""
    return _KIND_MAP.get(kind, ChunkKind.TUTORIAL)


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character spans of fenced code blocks, opening fence included."""
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    for match in _FENCE.finditer(text):
        if open_at is None:
            open_at = match.start()
        else:
            spans.append((open_at, match.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def inside_spans(position: int, spans: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Return the span containing the position, if any."""
    for span in spans:
        if span[0] < position < span[1]:
            return span
    return None


def split_code(content: str, limit: int) -> list[str]:
    """Cut a source file into pieces of at most `limit` characters at line boundaries."""
    if len(content) <= limit:
        return [content]
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for line in content.splitlines(keepends=True):
        if size + len(line) > limit and current:
            pieces.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        pieces.append("".join(current))
    return pieces


def task_text(task: Task) -> str:
    """Render a task as one block: title, statement, then numbered stages."""
    parts = [task.title, task.statement]
    parts.extend(f"Stage {stage.n}: {stage.text}" for stage in task.stages)
    if task.notes:
        parts.append(task.notes)
    return "\n\n".join(part.strip() for part in parts if part.strip())


def window_text(text: str, size: int, overlap: int) -> list[str]:
    """Slide a window of `size` over the text, ending windows on blank lines outside code."""
    if not text.strip():
        return []
    spans = fenced_spans(text)
    boundaries = [
        m.end() for m in _BLANK_LINE.finditer(text) if inside_spans(m.end(), spans) is None
    ]
    pieces: list[str] = []
    start = 0
    total = len(text)
    while start < total:
        end = min(start + size, total)
        if end < total:
            end = _snap_end(text, start, end, size, boundaries, spans)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= total:
            break
        start = max(end - overlap, start + 1)
    return pieces


def _snap_end(
    text: str,
    start: int,
    end: int,
    size: int,
    boundaries: list[int],
    spans: list[tuple[int, int]],
) -> int:
    """Move a window end to the last blank line after half a window, else past a code fence."""
    floor = start + size // 2
    candidates = [b for b in boundaries if floor < b <= end]
    if candidates:
        return candidates[-1]
    span = inside_spans(end, spans)
    if span is not None and span[1] - start <= 2 * size:
        return span[1]
    return end


def lab_task_chunks(chunker: Chunker, doc: LabDocument, start_idx: int) -> list[Chunk]:
    """Build one TASK chunk per example task of a lab."""
    chunks: list[Chunk] = []
    idx = start_idx
    for task in doc.tasks:
        text = task_text(task)
        if not text:
            continue
        chunks.append(
            chunker.make_chunk(
                doc,
                idx,
                text,
                ChunkKind.TASK,
                task_id=task.id,
                title=task.title,
                n_stages=len(task.stages),
            )
        )
        idx += 1
    return chunks


def lab_code_chunks(chunker: Chunker, doc: LabDocument, start_idx: int) -> list[Chunk]:
    """Build one CODE chunk per source file, splitting files above twice the chunk size."""
    chunks: list[Chunk] = []
    idx = start_idx
    for code_file in doc.code_files:
        pieces = split_code(code_file.content, 2 * chunker.chunk_size)
        for part, piece in enumerate(pieces):
            if not piece.strip():
                continue
            chunks.append(
                chunker.make_chunk(
                    doc,
                    idx,
                    piece,
                    ChunkKind.CODE,
                    ref=code_file.ref,
                    lang=code_file.lang,
                    part=part,
                    n_parts=len(pieces),
                )
            )
            idx += 1
    return chunks


@register("chunker", "fixed")
class FixedChunker(Chunker):
    name = "fixed"

    def chunk(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        kind = document_chunk_kind(doc.kind)
        for text in window_text(doc.text, self.chunk_size, self.overlap):
            chunks.append(self.make_chunk(doc, len(chunks), text, kind))
        if isinstance(doc, LabDocument):
            chunks.extend(lab_task_chunks(self, doc, len(chunks)))
            chunks.extend(lab_code_chunks(self, doc, len(chunks)))
        return chunks
