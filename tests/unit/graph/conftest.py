"""
Role:   Local fixtures for the graph unit tests: chunks, stub stores, stub searchers.
Input:  The shared `sample_documents` fixture from tests/conftest.py.
Output: Chunk lists, a StubGraphStore serving an in-memory DiGraph and a StubSearcher.
Flow:   `sample_chunks` builds hierarchical chunks matching the sample documents plus one chunk
        of a second strategy; the stubs let the searcher and the RAG run without Postgres.
"""

from typing import Any

import pytest

from rag_lab_generator.models import Chunk, ChunkKind, Course, Document, GraphEdge, GraphNode
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import Searcher, SearchFilters
from rag_lab_generator.retrieval.stores.graph_store import graph_from

LAB_ID = "sop1/lab/l1_filesystem"
LECTURE_ID = "sop1/lecture/w2/filesystem"


def make_chunk(
    document_id: str,
    idx: int,
    text: str,
    kind: ChunkKind,
    course: Course = Course.SOP1,
    lab_id: str | None = None,
    section_id: str | None = None,
    strategy: str = "hierarchical",
    **metadata: Any,
) -> Chunk:
    return Chunk(
        id=f"{strategy}:{document_id}:{idx}",
        document_id=document_id,
        course=course,
        lab_id=lab_id,
        kind=kind,
        strategy=strategy,
        idx=idx,
        text=text,
        section_id=section_id,
        metadata=metadata,
    )


@pytest.fixture
def sample_chunks(sample_documents: list[Document]) -> list[Chunk]:
    """Hierarchical chunks for the shared corpus plus one chunk of a second strategy."""
    lab = sample_documents[0]
    chunks: list[Chunk] = []
    for idx, section in enumerate(lab.sections):
        chunks.append(
            make_chunk(
                LAB_ID,
                idx,
                section.text,
                ChunkKind.TUTORIAL,
                lab_id=LAB_ID,
                section_id=section.id,
                title=section.title,
            )
        )
    offset = len(lab.sections)
    for n, task in enumerate(getattr(lab, "tasks", [])):
        body = task.statement + "\n" + "\n".join(s.text for s in task.stages)
        chunks.append(
            make_chunk(LAB_ID, offset + n, body, ChunkKind.TASK, lab_id=LAB_ID, task_id=task.id)
        )
    chunks.append(
        make_chunk(
            LAB_ID,
            offset + 2,
            'DIR* d = opendir(".");',
            ChunkKind.CODE,
            lab_id=LAB_ID,
            ref="src/prog1.c",
        )
    )
    for idx, section in enumerate(sample_documents[1].sections):
        chunks.append(
            make_chunk(LECTURE_ID, idx, section.text, ChunkKind.LECTURE, section_id=section.id)
        )
    chunks.append(make_chunk("sop1/info/rules", 0, "Each laboratory is graded.", ChunkKind.INFO))
    # a lab chunk that belongs to no section or task: only the lab node can own it
    chunks.append(
        make_chunk(
            LAB_ID,
            99,
            "Whole lab summary: the filesystem API from opendir to closedir.",
            ChunkKind.TUTORIAL,
            lab_id=LAB_ID,
        )
    )
    # a chunk of another strategy: must never leak into a hierarchical query
    chunks.append(
        make_chunk(
            LAB_ID,
            0,
            "Directories are read with opendir and readdir.",
            ChunkKind.TUTORIAL,
            lab_id=LAB_ID,
            section_id="browsing-a-directory",
            strategy="fixed",
        )
    )
    return chunks


class StubEmbedder(Embedder):
    """Constant embedder; the graph walk never uses it."""

    name = "stub"

    @property
    def dim(self) -> int:
        return 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 1.0]


class StubSearcher(Searcher):
    """Returns a fixed ranking; records the arguments it was called with."""

    name = "stub"

    def __init__(self, hits: list[Chunk] | None = None) -> None:
        self.hits = hits or []
        self.calls: list[tuple[str, int, SearchFilters]] = []
        self.store: Any = None
        self.embedder: Any = None
        self.settings: Any = None

    def search(self, query: str, k: int, filters: SearchFilters) -> list[Any]:
        from rag_lab_generator.models import ScoredChunk

        self.calls.append((query, k, filters))
        return [
            ScoredChunk(chunk=c, score=1.0 / (i + 1), source=self.name)
            for i, c in enumerate(self.hits[:k])
        ]


class StubGraphStore:
    """Serves an in-memory graph and chunk table with the GraphStore read interface."""

    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge], chunks: list[Chunk]) -> None:
        self._graph = graph_from(nodes, edges)
        self._chunks = {c.id: c for c in chunks}
        self._nodes = {n.id: n for n in nodes}

    def load_graph(self, refresh: bool = False) -> Any:
        return self._graph

    def fetch_chunks(self, ids: list[str]) -> dict[str, Chunk]:
        return {i: self._chunks[i] for i in ids if i in self._chunks}

    def nodes_for_chunks(self, chunk_ids: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for node in self._nodes.values():
            for chunk_id in node.chunk_ids:
                if chunk_id in chunk_ids:
                    result.setdefault(chunk_id, []).append(node.id)
        return {key: sorted(value) for key, value in result.items()}

    def chunks_for_nodes(self, node_ids: list[str]) -> dict[str, list[str]]:
        return {n: list(self._nodes[n].chunk_ids) for n in node_ids if n in self._nodes}
