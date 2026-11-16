"""
Role:   Unit tests for the graph RAG: trace contents and the task/section sibling augmentation.
Input:  StubGraphStore, StubSearcher and StubEmbedder from the local conftest.
Output: Assertions on the RetrievedContext trace and on the extra section chunks.
Flow:   Builds a task node sharing an api function with a section node, runs retrieve() and
        checks that the section chunk is added even when k only admits the task chunk.
"""

import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import ChunkKind, Course, EdgeKind, GraphEdge, GraphNode, NodeKind
from rag_lab_generator.retrieval.rag.graph_rag import GraphRAG
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.searchers.graph_walk import GraphWalkSearcher
from tests.unit.graph.conftest import StubEmbedder, StubGraphStore, StubSearcher, make_chunk

DOC = "sop1/lab/l1"
TASK_CHUNK = f"hierarchical:{DOC}:10"
SECTION_CHUNK = f"hierarchical:{DOC}:0"


def _fixture() -> tuple[list[GraphNode], list[GraphEdge], list]:
    chunks = [
        make_chunk(DOC, 0, "opendir tutorial", ChunkKind.TUTORIAL, lab_id=DOC, section_id="a"),
        make_chunk(DOC, 10, "write a scanner", ChunkKind.TASK, lab_id=DOC, task_id="example1"),
    ]
    nodes = [
        GraphNode(
            id="t1",
            kind=NodeKind.TASK,
            label="Directory scanner",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[TASK_CHUNK],
        ),
        GraphNode(
            id="s:a",
            kind=NodeKind.SECTION,
            label="Browsing",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[SECTION_CHUNK],
        ),
        GraphNode(id="api:opendir", kind=NodeKind.API_FUNCTION, label="opendir"),
    ]
    edges = [
        GraphEdge(src="t1", dst="api:opendir", kind=EdgeKind.USES_API, weight=2.0),
        GraphEdge(src="s:a", dst="api:opendir", kind=EdgeKind.USES_API, weight=4.0),
    ]
    return nodes, edges, chunks


def test_trace_contents(settings: Settings) -> None:
    nodes, edges, chunks = _fixture()
    store = StubGraphStore(nodes, edges, chunks)
    two_hops = settings.model_copy(update={"graph_hops": 2})
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), two_hops, inner=StubSearcher([chunks[1]])
    )
    rag = GraphRAG(walker, store, settings)
    context = rag.retrieve("directory scanner", 5, SearchFilters(strategy="hierarchical"))
    assert context.rag == "graph"
    assert context.query == "directory scanner"
    assert context.trace["seed_nodes"] == ["t1"]
    assert set(context.trace["seed_weights"]) == {"t1"}
    assert context.trace["activated_nodes"] == 3
    assert context.trace["latency_ms"] >= 0.0
    assert context.trace["paths"][TASK_CHUNK] == ["t1"]
    assert context.trace["paths"][SECTION_CHUNK] == ["t1", "api:opendir", "s:a"]


def test_task_gets_sibling_section_chunk(settings: Settings) -> None:
    nodes, edges, chunks = _fixture()
    store = StubGraphStore(nodes, edges, chunks)
    two_hops = settings.model_copy(update={"graph_hops": 2})
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), two_hops, inner=StubSearcher([chunks[1]])
    )
    rag = GraphRAG(walker, store, settings)
    context = rag.retrieve("scanner", 1, SearchFilters(strategy="hierarchical"))
    assert [sc.chunk.id for sc in context.chunks] == [TASK_CHUNK, SECTION_CHUNK]
    assert context.chunks[1].source == "graph_rag_sibling"
    assert context.chunks[1].score == pytest.approx(context.chunks[0].score * 0.5)
    assert context.trace["siblings"] == 1


def test_plain_searcher_is_wrapped(settings: Settings) -> None:
    nodes, edges, chunks = _fixture()
    store = StubGraphStore(nodes, edges, chunks)
    rag = GraphRAG(StubSearcher([chunks[1]]), store, settings.model_copy(update={"graph_hops": 2}))
    assert isinstance(rag.searcher, GraphWalkSearcher)
    assert rag.searcher.inner_name == "stub"
    context = rag.retrieve("scanner", 5, SearchFilters(strategy="hierarchical"))
    assert {sc.chunk.id for sc in context.chunks} == {TASK_CHUNK, SECTION_CHUNK}
