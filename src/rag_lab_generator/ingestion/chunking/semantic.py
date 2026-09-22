"""
Role:   Embedding-driven chunker: groups consecutive paragraphs that stay topically similar.
Input:  Document / LabDocument; Settings (chunk_size, embedding_provider) through Chunker.
Output: List of Chunk whose text is a run of paragraphs above the similarity threshold.
Flow:   Splits the text into paragraphs (a fenced code block is one paragraph), embeds them with
        the configured embedder, then extends the current group while cosine(group centroid,
        next paragraph) >= similarity_threshold and the group stays below chunk_size; a new
        group repeats the previous last paragraph when it fits the overlap budget. Pieces below
        MIN_PIECE_RATIO * chunk_size are folded into a neighbour so a lone heading or a two-line
        bullet never becomes a chunk. split_text() is reused by the hierarchical chunker.
"""

import re
from typing import Any

import numpy as np
from numpy.typing import NDArray

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.chunking.base import Chunker
from rag_lab_generator.ingestion.chunking.fixed import (
    document_chunk_kind,
    lab_code_chunks,
    lab_task_chunks,
    window_text,
)
from rag_lab_generator.models import Chunk, Document, LabDocument
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder

_FENCE = re.compile(r"^\s*```")
MIN_PIECE_RATIO = 0.25


def split_paragraphs(text: str) -> list[str]:
    """Split a text into non-empty paragraphs separated by blank lines; fenced code stays whole."""
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\n".join(current).strip())
    return [p for p in paragraphs if p]


@register("chunker", "semantic")
class SemanticChunker(Chunker):
    name = "semantic"
    similarity_threshold: float = 0.75

    def __init__(self, settings: Settings, embedder: Embedder | None = None) -> None:
        super().__init__(settings)
        self._embedder = embedder
        self._embedder_unavailable = False

    def chunk(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        kind = document_chunk_kind(doc.kind)
        for text in self.split_text(doc.text):
            chunks.append(self.make_chunk(doc, len(chunks), text, kind))
        if isinstance(doc, LabDocument):
            chunks.extend(lab_task_chunks(self, doc, len(chunks)))
            chunks.extend(lab_code_chunks(self, doc, len(chunks)))
        return chunks

    def split_text(self, text: str, overlap_ratio: float | None = None) -> list[str]:
        """Group paragraphs of one text into semantically coherent pieces below chunk_size."""
        paragraphs = split_paragraphs(text)
        if not paragraphs:
            return []
        if len(paragraphs) == 1:
            return self._enforce_size(paragraphs)
        ratio = self.settings.chunk_overlap_ratio if overlap_ratio is None else overlap_ratio
        budget = int(self.chunk_size * ratio)
        vectors = self._embed(paragraphs)
        groups = (
            self._group_by_size(paragraphs, budget)
            if vectors is None
            else self._group_by_similarity(paragraphs, vectors, budget)
        )
        return self._merge_small(self._enforce_size(["\n\n".join(group) for group in groups]))

    def _group_by_similarity(
        self, paragraphs: list[str], vectors: NDArray[np.float64], budget: int
    ) -> list[list[str]]:
        """Extend a group while its centroid stays close to the next paragraph."""
        groups: list[list[str]] = []
        current = [0]
        for i in range(1, len(paragraphs)):
            centroid = vectors[current].mean(axis=0)
            similarity = _cosine(centroid, vectors[i])
            size = sum(len(paragraphs[j]) + 2 for j in current)
            fits = size + len(paragraphs[i]) < self.chunk_size
            if similarity >= self.similarity_threshold and fits:
                current.append(i)
                continue
            groups.append([paragraphs[j] for j in current])
            previous = current[-1]
            current = [previous, i] if len(paragraphs[previous]) <= budget else [i]
        groups.append([paragraphs[j] for j in current])
        return groups

    def _group_by_size(self, paragraphs: list[str], budget: int) -> list[list[str]]:
        """Fall back to size-only grouping when no embedder can be created."""
        groups: list[list[str]] = []
        current = [0]
        for i in range(1, len(paragraphs)):
            size = sum(len(paragraphs[j]) + 2 for j in current)
            if size + len(paragraphs[i]) < self.chunk_size:
                current.append(i)
                continue
            groups.append([paragraphs[j] for j in current])
            previous = current[-1]
            current = [previous, i] if len(paragraphs[previous]) <= budget else [i]
        groups.append([paragraphs[j] for j in current])
        return groups

    def _merge_small(self, pieces: list[str]) -> list[str]:
        """Fold pieces below the minimum size into their predecessor while chunk_size allows."""
        minimum = int(self.chunk_size * MIN_PIECE_RATIO)
        merged: list[str] = []
        for piece in pieces:
            if merged and (len(merged[-1]) < minimum or len(piece) < minimum):
                # Drop the overlap paragraph the piece repeats from its predecessor.
                tail = split_paragraphs(merged[-1])[-1]
                body = piece[len(tail) :].lstrip() if piece.startswith(tail) else piece
                joined = f"{merged[-1]}\n\n{body}" if body else merged[-1]
                if len(joined) <= self.chunk_size:
                    merged[-1] = joined
                    continue
            merged.append(piece)
        return merged

    def _enforce_size(self, pieces: list[str]) -> list[str]:
        """Hard-split pieces that a single oversized paragraph pushed above chunk_size."""
        out: list[str] = []
        for piece in pieces:
            if len(piece) <= self.chunk_size:
                if piece.strip():
                    out.append(piece.strip())
                continue
            out.extend(window_text(piece, self.chunk_size, self.overlap))
        return out

    def _embed(self, paragraphs: list[str]) -> NDArray[np.float64] | None:
        embedder = self._get_embedder()
        if embedder is None:
            return None
        return np.asarray(embedder.embed_documents(paragraphs), dtype=np.float64)

    def _get_embedder(self) -> Embedder | None:
        """Create the configured embedder once; treat any failure as 'no embeddings available'."""
        if self._embedder is not None or self._embedder_unavailable:
            return self._embedder
        try:
            created: Any = registry.create(
                "embedder", self.settings.embedding_provider, settings=self.settings
            )
        except Exception:
            self._embedder_unavailable = True
            return None
        self._embedder = created
        return self._embedder


def _cosine(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / norm)
