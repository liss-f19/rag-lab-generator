"""
Role:   Integration tests for GraphStore against a real Postgres (docker compose up -d db).
Input:  A running database at Settings.database_url; the test seeds its own document and chunks.
Output: Assertions on the replace_graph/load_graph round trip and the chunk<->node lookups.
Flow:   Applies the schema, writes one document with three chunks, replaces the whole graph with
        a small fixture graph, exercises the readers and removes every row it created.
        Note: replace_graph rewrites the graph tables, so a corpus graph must be rebuilt after.
"""

from collections.abc import Iterator

import psycopg
import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    Document,
    DocumentKind,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
    Section,
)
from rag_lab_generator.retrieval.stores.graph_store import GraphStore

pytestmark = pytest.mark.integration

STRATEGY = "test_graph"
DOC_ID = "test/lab/graph_integration"
LAB_NODE = DOC_ID
SECTION_NODE = f"{DOC_ID}#section:browsing"
API_NODE = "api:opendir"
CHUNKS = {
    0: "Directories are read with opendir and readdir.",
    1: "Call closedir when the iteration is finished.",
    2: "Write a program that counts directory entries.",
}


def _chunk_id(idx: int) -> str:
    return f"{STRATEGY}:{DOC_ID}:{idx}"


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(embedding_provider="fake", embedding_dim=64, graph_hops=2)


@pytest.fixture(scope="module")
def store(settings: Settings) -> Iterator[GraphStore]:
    store = GraphStore(settings)
    try:
        with store.connection():
            pass
    except psycopg.Error as exc:
        pytest.skip(f"postgres not reachable at {settings.database_url}: {exc}")
    store.apply_schema()
    store.upsert_documents(
        [
            Document(
                id=DOC_ID,
                course=Course.SOP1,
                kind=DocumentKind.LAB,
                title="Graph integration lab",
                sections=[Section(id="browsing", title="Browsing", order=0, text=CHUNKS[0])],
            )
        ]
    )
    store.upsert_chunks(
        [
            Chunk(
                id=_chunk_id(idx),
                document_id=DOC_ID,
                course=Course.SOP1,
                lab_id=DOC_ID,
                kind=ChunkKind.TUTORIAL,
                strategy=STRATEGY,
                idx=idx,
                text=text,
                section_id="browsing",
            )
            for idx, text in CHUNKS.items()
        ]
    )
    yield store
    with store.connection() as conn:
        conn.execute("DELETE FROM edges")
        conn.execute("DELETE FROM nodes")
        conn.execute("DELETE FROM documents WHERE id = %s", (DOC_ID,))
        conn.commit()


def _fixture_graph() -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes = [
        GraphNode(
            id=LAB_NODE,
            kind=NodeKind.LAB,
            label="Graph integration lab",
            course=Course.SOP1,
            lab_id=DOC_ID,
            document_id=DOC_ID,
            chunk_ids=[_chunk_id(0), _chunk_id(1), _chunk_id(2)],
            properties={"number": "1", "topics": ["opendir"]},
        ),
        GraphNode(
            id=SECTION_NODE,
            kind=NodeKind.SECTION,
            label="Browsing",
            course=Course.SOP1,
            lab_id=DOC_ID,
            document_id=DOC_ID,
            chunk_ids=[_chunk_id(0), _chunk_id(1)],
        ),
        GraphNode(
            id=API_NODE,
            kind=NodeKind.API_FUNCTION,
            label="opendir",
            # a chunk id that does not exist must not break the insert
            chunk_ids=[_chunk_id(0), f"{STRATEGY}:missing:99"],
        ),
    ]
    edges = [
        GraphEdge(src=LAB_NODE, dst=SECTION_NODE, kind=EdgeKind.CONTAINS),
        GraphEdge(src=SECTION_NODE, dst=API_NODE, kind=EdgeKind.USES_API, weight=3.0),
    ]
    return nodes, edges


def test_replace_graph_round_trip(store: GraphStore) -> None:
    nodes, edges = _fixture_graph()
    assert store.replace_graph(nodes, edges) == {"nodes": 3, "edges": 2}
    graph = store.load_graph(refresh=True)
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 2
    assert graph.nodes[LAB_NODE]["kind"] == "lab"
    assert graph.nodes[LAB_NODE]["properties"]["topics"] == ["opendir"]
    assert graph.nodes[SECTION_NODE]["chunk_ids"] == [_chunk_id(0), _chunk_id(1)]
    assert graph.edges[SECTION_NODE, API_NODE, "uses_api"]["kind"] == "uses_api"
    assert graph.edges[SECTION_NODE, API_NODE, "uses_api"]["weight"] == 3.0
    # the dangling chunk id was silently skipped by the FK-safe insert
    assert graph.nodes[API_NODE]["chunk_ids"] == [_chunk_id(0)]


def test_chunk_and_node_lookups(store: GraphStore) -> None:
    store.replace_graph(*_fixture_graph())
    assert store.nodes_for_chunks([_chunk_id(0)]) == {
        _chunk_id(0): sorted([API_NODE, LAB_NODE, SECTION_NODE])
    }
    assert store.nodes_for_chunks([]) == {}
    assert store.chunks_for_nodes([SECTION_NODE]) == {SECTION_NODE: [_chunk_id(0), _chunk_id(1)]}


def test_find_nodes_is_case_insensitive(store: GraphStore) -> None:
    store.replace_graph(*_fixture_graph())
    found = store.find_nodes("OPENDIR")
    assert [n.id for n in found] == [API_NODE]
    assert store.find_nodes("brow", kinds=[NodeKind.SECTION])[0].id == SECTION_NODE
    assert store.find_nodes("brow", kinds=[NodeKind.API_FUNCTION]) == []


def test_stats_counts_kinds(store: GraphStore) -> None:
    store.replace_graph(*_fixture_graph())
    stats = store.stats()
    assert stats["nodes"] == 3
    assert stats["edges"] == 2
    assert stats["node:api_function"] == 1
    assert stats["edge:contains"] == 1
    assert stats["node_chunks"] == 6


def test_upsert_nodes_refreshes_labels_and_links(store: GraphStore) -> None:
    nodes, edges = _fixture_graph()
    store.replace_graph(nodes, edges)
    updated = nodes[1].model_copy(update={"label": "Browsing v2", "chunk_ids": [_chunk_id(2)]})
    store.upsert_nodes([updated])
    graph = store.load_graph(refresh=True)
    assert graph.nodes[SECTION_NODE]["label"] == "Browsing v2"
    assert graph.nodes[SECTION_NODE]["chunk_ids"] == [_chunk_id(2)]
