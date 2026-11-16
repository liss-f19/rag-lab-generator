"""Structure-aware segmentation of extracted text into indexable fragments (FR-06).

Fragments never cross a section or page boundary, so each one keeps an exact
section path and page number. Paragraphs are packed greedily up to the size
limit; fenced code blocks are not split unless they alone exceed it. Only text
longer than the limit is cut into overlapping windows.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from rag_lab_generator.domain.models import TextBlock

_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class TextPiece:
    content: str
    section_path: tuple[str, ...]
    page_number: int | None


class StructuredChunker:
    def __init__(self, max_chars: int = 1200, overlap_chars: int = 150) -> None:
        if max_chars < 100:
            raise ValueError("max_chars must be at least 100")
        if not 0 <= overlap_chars < max_chars // 2:
            raise ValueError("overlap_chars must be in [0, max_chars / 2)")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def split(self, blocks: Sequence[TextBlock]) -> list[TextPiece]:
        pieces: list[TextPiece] = []
        for block in blocks:
            for content in self._pack(_paragraphs(block.text)):
                pieces.append(TextPiece(content, block.section_path, block.page_number))
        return pieces

    def _pack(self, paragraphs: list[str]) -> Iterator[str]:
        current: list[str] = []
        size = 0
        for paragraph in paragraphs:
            if len(paragraph) > self.max_chars:
                if current:
                    yield "\n\n".join(current)
                    current, size = [], 0
                yield from self._windows(paragraph)
                continue
            added = len(paragraph) + (2 if current else 0)
            if current and size + added > self.max_chars:
                yield "\n\n".join(current)
                current, size = [], 0
                added = len(paragraph)
            current.append(paragraph)
            size += added
        if current:
            yield "\n\n".join(current)

    def _windows(self, text: str) -> Iterator[str]:
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            if end < len(text):
                lower = start + self.max_chars // 2
                cut = max(text.rfind("\n", lower, end), text.rfind(" ", lower, end))
                if cut > start:
                    end = cut
            piece = text[start:end].strip()
            if piece:
                yield piece
            if end >= len(text):
                return
            next_start = end - self.overlap_chars
            if next_start <= start:
                next_start = end
            boundary = text.find(" ", next_start, end)
            start = boundary + 1 if boundary != -1 else next_start


def _paragraphs(text: str) -> list[str]:
    """Split on blank lines, keeping each fenced code block in one paragraph."""
    paragraphs: list[str] = []
    lines: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
        if fence is None and not line.strip() and not match:
            if lines:
                paragraphs.append("\n".join(lines).strip("\n"))
                lines = []
            continue
        lines.append(line)
    if lines:
        paragraphs.append("\n".join(lines).strip("\n"))
    return [p for p in paragraphs if p.strip()]
