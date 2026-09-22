"""
Role:   Unit tests for the graph_walk searcher on a tiny hand-built graph.
Input:  StubGraphStore, StubSearcher and StubEmbedder from the local conftest.
Output: Assertions on decay, hop limit, strategy filtering, seed penalty and path explanations.
Flow:   Builds five nodes with known edge kinds, runs the searcher and checks the scores.
"""

from typing import Any

import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
)
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.searchers.graph_walk import GraphWalkSearcher
from tests.unit.graph.conftest import StubEmbedder, StubGraphStore, StubSearcher, make_chunk

DOC = "sop1/lab/l1"


def _chunk(idx: int, strategy: str = "hierarchical", kind: ChunkKind = ChunkKind.TUTORIAL) -> Chunk:
    return make_chunk(DOC, idx, f"text {idx}", kind, lab_id=DOC, strategy=strategy)


@pytest.fixture
def tiny_graph() -> tuple[list[GraphNode], list[GraphEdge], list[Chunk]]:
    """lab -CONTAINS-> a -USES_API-> fork <-USES_API- b -CONTAINS-> c."""
    chunks = [_chunk(i) for i in range(5)] + [_chunk(9, strategy="fixed")]
    nodes = [
        GraphNode(
            id="lab1",
            kind=NodeKind.LAB,
            label="Lab 1",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:3"],
        ),
        GraphNode(
            id="s:a",
            kind=NodeKind.SECTION,
            label="Section A",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:0", f"fixed:{DOC}:9"],
        ),
        GraphNode(
            id="api:fork",
            kind=NodeKind.API_FUNCTION,
            label="fork",
            chunk_ids=[f"hierarchical:{DOC}:1"],
        ),
        GraphNode(
            id="s:b",
            kind=NodeKind.SECTION,
            label="Section B",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:2"],
        ),
        GraphNode(
            id="s:c",
            kind=NodeKind.SECTION,
            label="Section C",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:4"],
        ),
    ]
    edges = [
        GraphEdge(src="lab1", dst="s:a", kind=EdgeKind.CONTAINS),
        GraphEdge(src="s:a", dst="api:fork", kind=EdgeKind.USES_API, weight=3.0),
        GraphEdge(src="s:b", dst="api:fork", kind=EdgeKind.USES_API, weight=1.0),
        GraphEdge(src="s:b", dst="s:c", kind=EdgeKind.CONTAINS),
    ]
    return nodes, edges, chunks


def _searcher(
    tiny_graph: tuple[list[GraphNode], list[GraphEdge], list[Chunk]],
    settings: Settings,
    hits: list[Chunk],
    hops: int = 2,
) -> tuple[GraphWalkSearcher, StubGraphStore]:
    nodes, edges, chunks = tiny_graph
    store = StubGraphStore(nodes, edges, chunks)
    inner = StubSearcher(hits)
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), settings.model_copy(update={"graph_hops": hops}), inner=inner
    )
    return walker, store


def test_decay_per_edge_kind(tiny_graph: Any, settings: Settings) -> None:
    """s:a owns 2 chunks, so its seed is 1.0 / log2(4) = 0.5 and decays from there."""
    _, _, chunks = tiny_graph
    walker, _ = _searcher(tiny_graph, settings, [chunks[0]])
    results = walker.search("anything", 10, SearchFilters(strategy="hierarchical"))
    scores = {r.chunk.id: round(r.score, 4) for r in results}
    # best path (the searcher's own 1.0) plus the bonus for one further corroboration
    assert scores[f"hierarchical:{DOC}:0"] == 1.104
    assert scores[f"hierarchical:{DOC}:3"] == 0.45
    assert scores[f"hierarchical:{DOC}:1"] == 0.4
    assert scores[f"hierarchical:{DOC}:2"] == 0.32
    assert all(r.source == "graph_walk" for r in results)
    # every score is distinct, so the order never falls back to the chunk id
    assert len(set(scores.values())) == len(scores)


def test_hop_limit(tiny_graph: Any, settings: Settings) -> None:
    _, _, chunks = tiny_graph
    walker, _ = _searcher(tiny_graph, settings, [chunks[0]], hops=1)
    ids = {r.chunk.id for r in walker.search("q", 10, SearchFilters(strategy="hierarchical"))}
    assert ids == {f"hierarchical:{DOC}:0", f"hierarchical:{DOC}:3", f"hierarchical:{DOC}:1"}
    walker3, _ = _searcher(tiny_graph, settings, [chunks[0]], hops=3)
    ids3 = {r.chunk.id for r in walker3.search("q", 10, SearchFilters(strategy="hierarchical"))}
    assert f"hierarchical:{DOC}:4" in ids3


def test_strategy_filter_excludes_other_chunkers(tiny_graph: Any, settings: Settings) -> None:
    _, _, chunks = tiny_graph
    walker, _ = _searcher(tiny_graph, settings, [chunks[0]])
    ids = [r.chunk.id for r in walker.search("q", 10, SearchFilters(strategy="hierarchical"))]
    assert all(i.startswith("hierarchical:") for i in ids)
    assert f"fixed:{DOC}:9" not in ids


def test_path_explains_every_result(tiny_graph: Any, settings: Settings) -> None:
    _, _, chunks = tiny_graph
    walker, _ = _searcher(tiny_graph, settings, [chunks[0]])
    paths = {
        r.chunk.id: r.chunk.metadata["path"]
        for r in walker.search("q", 10, SearchFilters(strategy="hierarchical"))
    }
    assert paths[f"hierarchical:{DOC}:0"] == ["s:a"]
    assert paths[f"hierarchical:{DOC}:1"] == ["s:a", "api:fork"]
    assert paths[f"hierarchical:{DOC}:2"] == ["s:a", "api:fork", "s:b"]
    assert walker.last_trace["seed_nodes"] == ["s:a"]
    assert walker.last_trace["activated_nodes"] == 4


def test_term_seed_is_hub_damped(tiny_graph: Any, settings: Settings) -> None:
    """api:fork owns 1 chunk, so its term seed is 0.5 / log2(3) rather than a flat 0.5."""
    walker, _ = _searcher(tiny_graph, settings, [])
    results = walker.search("how does fork work", 10, SearchFilters(strategy="hierarchical"))
    scores = {r.chunk.id: round(r.score, 4) for r in results}
    assert walker.last_trace["seed_nodes"] == ["api:fork"]
    assert walker.last_trace["seed_weights"] == {"api:fork": 0.3155}
    assert scores[f"hierarchical:{DOC}:1"] == 0.3155
    assert scores[f"hierarchical:{DOC}:0"] == 0.2524


def test_bigger_hub_seeds_more_weakly(settings: Settings) -> None:
    """The same term seed is worth less when its node owns more of the corpus."""
    rare = GraphNode(
        id="concept:fifo", kind=NodeKind.CONCEPT, label="fifo", chunk_ids=[f"hierarchical:{DOC}:0"]
    )
    hub = GraphNode(
        id="concept:signal",
        kind=NodeKind.CONCEPT,
        label="signal",
        chunk_ids=[f"hierarchical:{DOC}:{i}" for i in range(30)],
    )
    chunks = [_chunk(i) for i in range(30)]
    store = StubGraphStore([rare, hub], [], chunks)
    walker = GraphWalkSearcher(store, StubEmbedder(settings), settings, inner=StubSearcher([]))
    walker.search("fifo and signal", 5, SearchFilters(strategy="hierarchical"))
    weights = walker.last_trace["seed_weights"]
    assert weights["concept:fifo"] > weights["concept:signal"]


def test_several_seeds_accumulate(settings: Settings) -> None:
    """A chunk reached from two seeds outranks one reached from a single seed of equal weight."""
    shared = GraphNode(
        id="s:shared",
        kind=NodeKind.SECTION,
        label="Shared",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:0"],
    )
    lonely = GraphNode(
        id="s:lonely",
        kind=NodeKind.SECTION,
        label="Lonely",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:1"],
    )
    left = GraphNode(id="api:fork", kind=NodeKind.API_FUNCTION, label="fork", chunk_ids=[])
    right = GraphNode(id="api:exec", kind=NodeKind.API_FUNCTION, label="exec", chunk_ids=[])
    edges = [
        GraphEdge(src="s:shared", dst="api:fork", kind=EdgeKind.USES_API),
        GraphEdge(src="s:shared", dst="api:exec", kind=EdgeKind.USES_API),
        GraphEdge(src="s:lonely", dst="api:fork", kind=EdgeKind.USES_API),
    ]
    chunks = [_chunk(0), _chunk(1)]
    store = StubGraphStore([shared, lonely, left, right], edges, chunks)
    walker = GraphWalkSearcher(store, StubEmbedder(settings), settings, inner=StubSearcher([]))
    results = walker.search("fork and exec", 5, SearchFilters(strategy="hierarchical"))
    scores = {r.chunk.id: r.score for r in results}
    assert scores[f"hierarchical:{DOC}:0"] > scores[f"hierarchical:{DOC}:1"]


def test_inner_rank_breaks_ties(settings: Settings) -> None:
    """Two chunks of one hub node tie on activation; the searcher's own rank decides."""
    node = GraphNode(
        id="lecture:x",
        kind=NodeKind.LECTURE,
        label="Lecture X",
        course=Course.SOP1,
        chunk_ids=[f"hierarchical:{DOC}:{i}" for i in range(4)],
    )
    chunks = [_chunk(i, kind=ChunkKind.LECTURE) for i in range(4)]
    store = StubGraphStore([node], [], chunks)
    # the searcher returns chunk 2 first, so it must come out on top of its node siblings
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), settings, inner=StubSearcher([chunks[2], chunks[3]])
    )
    results = walker.search("q", 4, SearchFilters(strategy="hierarchical"))
    assert [r.chunk.id for r in results][:2] == [
        f"hierarchical:{DOC}:2",
        f"hierarchical:{DOC}:3",
    ]


def test_bigram_label_seed(settings: Settings) -> None:
    nodes = [
        GraphNode(
            id="concept:shared memory",
            kind=NodeKind.CONCEPT,
            label="shared memory",
            chunk_ids=[f"hierarchical:{DOC}:7"],
        ),
    ]
    chunks = [_chunk(7)]
    store = StubGraphStore(nodes, [], chunks)
    walker = GraphWalkSearcher(store, StubEmbedder(settings), settings, inner=StubSearcher([]))
    results = walker.search(
        "explain shared memory mappings", 5, SearchFilters(strategy="hierarchical")
    )
    assert [r.chunk.id for r in results] == [f"hierarchical:{DOC}:7"]


def test_course_and_kind_filters(tiny_graph: Any, settings: Settings) -> None:
    _, _, chunks = tiny_graph
    walker, _ = _searcher(tiny_graph, settings, [chunks[0]])
    empty = walker.search("q", 10, SearchFilters(strategy="hierarchical", course="sop2"))
    assert empty == []
    kinds = walker.search("q", 10, SearchFilters(strategy="hierarchical", kinds=["task"]))
    assert kinds == []


def test_inner_searcher_receives_filters(tiny_graph: Any, settings: Settings) -> None:
    nodes, edges, chunks = tiny_graph
    inner = StubSearcher([chunks[0]])
    walker = GraphWalkSearcher(
        StubGraphStore(nodes, edges, chunks), StubEmbedder(settings), settings, inner=inner
    )
    filters = SearchFilters(strategy="hierarchical", lab_id=DOC)
    walker.search("query text", 4, filters)
    assert inner.calls == [("query text", 4, filters)]
    assert walker.last_trace["inner_searcher"] == "stub"


def test_course_hub_does_not_spread(settings: Settings) -> None:
    """A course node is reachable but never relays activation to its other documents."""
    nodes = [
        GraphNode(
            id="course:sop1",
            kind=NodeKind.COURSE,
            label="sop1",
            course=Course.SOP1,
            chunk_ids=[],
        ),
        GraphNode(
            id="lab1",
            kind=NodeKind.LAB,
            label="Lab 1",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:0"],
        ),
        GraphNode(
            id="lab2",
            kind=NodeKind.LAB,
            label="Lab 2",
            course=Course.SOP1,
            lab_id=DOC,
            chunk_ids=[f"hierarchical:{DOC}:1"],
        ),
    ]
    edges = [
        GraphEdge(src="course:sop1", dst="lab1", kind=EdgeKind.CONTAINS),
        GraphEdge(src="course:sop1", dst="lab2", kind=EdgeKind.CONTAINS),
    ]
    chunks = [_chunk(0), _chunk(1)]
    store = StubGraphStore(nodes, edges, chunks)
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), settings, inner=StubSearcher([chunks[0]])
    )
    ids = [r.chunk.id for r in walker.search("q", 10, SearchFilters(strategy="hierarchical"))]
    assert ids == [f"hierarchical:{DOC}:0"]


def test_code_chunks_are_capped_in_the_result(settings: Settings) -> None:
    """Source listings may take at most code_chunk_share of the returned k."""
    node = GraphNode(
        id="s:a",
        kind=NodeKind.SECTION,
        label="Section A",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:{i}" for i in range(10)],
    )
    # six code chunks and four prose ones, all tied on activation from the one seed
    chunks = [_chunk(i, kind=ChunkKind.CODE) for i in range(6)]
    chunks += [_chunk(i, kind=ChunkKind.TUTORIAL) for i in range(6, 10)]
    store = StubGraphStore([node], [], chunks)
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), settings, inner=StubSearcher([chunks[0]])
    )
    results = walker.search("q", 4, SearchFilters(strategy="hierarchical"))
    kinds = [r.chunk.kind for r in results]
    assert len(results) == 4
    # int(4 * 0.25) = 1 code chunk, the rest filled with the best prose candidates
    assert kinds.count(ChunkKind.CODE) == 1
    assert kinds.count(ChunkKind.TUTORIAL) == 3


def test_arrival_at_a_code_file_node_is_damped(settings: Settings) -> None:
    """A CODE_FILE neighbour receives code_node_factor of the usual decayed activation."""
    section = GraphNode(
        id="s:a",
        kind=NodeKind.SECTION,
        label="A",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:0"],
    )
    prose = GraphNode(
        id="s:b",
        kind=NodeKind.SECTION,
        label="B",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:1"],
    )
    code = GraphNode(
        id="c:x",
        kind=NodeKind.CODE_FILE,
        label="x.c",
        course=Course.SOP1,
        lab_id=DOC,
        chunk_ids=[f"hierarchical:{DOC}:2"],
    )
    edges = [
        GraphEdge(src="s:a", dst="s:b", kind=EdgeKind.CONTAINS),
        GraphEdge(src="s:a", dst="c:x", kind=EdgeKind.CONTAINS),
    ]
    chunks = [_chunk(0), _chunk(1), _chunk(2, kind=ChunkKind.CODE)]
    store = StubGraphStore([section, prose, code], edges, chunks)
    walker = GraphWalkSearcher(
        store, StubEmbedder(settings), settings, inner=StubSearcher([chunks[0]])
    )
    scores = {
        r.chunk.id: r.score for r in walker.search("q", 5, SearchFilters(strategy="hierarchical"))
    }
    # same CONTAINS edge from the same seed, so the ratio is exactly code_node_factor
    ratio = scores[f"hierarchical:{DOC}:2"] / scores[f"hierarchical:{DOC}:1"]
    assert ratio == pytest.approx(GraphWalkSearcher.code_node_factor)


def test_a_lab_is_seeded_by_its_own_name(settings: Settings) -> None:
    """A lab with no api nodes is still reachable through its name."""
    lab = GraphNode(
        id="sop2/netcat",
        kind=NodeKind.LAB,
        label="Netcat and the network tools",
        course=Course.SOP2,
        lab_id="sop2/netcat",
        chunk_ids=[],
        properties={"slug": "netcat"},
    )
    section = GraphNode(
        id="sop2/netcat#section:tcp",
        kind=NodeKind.SECTION,
        label="TCP",
        course=Course.SOP2,
        lab_id="sop2/netcat",
        chunk_ids=[f"hierarchical:{DOC}:0"],
    )
    edges = [GraphEdge(src="sop2/netcat", dst="sop2/netcat#section:tcp", kind=EdgeKind.CONTAINS)]
    store = StubGraphStore([lab, section], edges, [_chunk(0)])
    walker = GraphWalkSearcher(store, StubEmbedder(settings), settings, inner=StubSearcher([]))
    results = walker.search(
        "what does the netcat lab cover", 5, SearchFilters(strategy="hierarchical")
    )
    assert walker.last_trace["seed_nodes"] == ["sop2/netcat"]
    assert [r.chunk.id for r in results] == [f"hierarchical:{DOC}:0"]
