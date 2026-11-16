"""
Role:   Unit tests of the node describer: source selection, caching by hash and prompt shape.
Input:  An in-memory stand-in for GraphStore and the FakeLLM; no database, no network.
Output: Assertions; no side effects.
Flow:   Builds a lab node with task, tutorial, lecture and code chunks, runs describe_nodes
        twice and checks that the second run is a no-op, that --force regenerates, that the
        prompt ranks lab text before code and that empty nodes are skipped.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.generation.llm.fake import FakeLLM
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    GraphNode,
    NodeDescription,
    NodeKind,
)
from rag_lab_generator.retrieval.graph.describer import (
    build_user_prompt,
    describe_nodes,
    select_sources,
    source_hash,
)


def _chunk(chunk_id: str, kind: ChunkKind, text: str, idx: int = 0) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id="sop1/l4",
        course=Course.SOP1,
        lab_id="sop1/l4",
        kind=kind,
        strategy="hierarchical",
        idx=idx,
        text=text,
        section_id=f"s{idx}",
    )


class _Store:
    """GraphStore stand-in holding nodes, chunks and descriptions in dictionaries."""

    def __init__(self, nodes: list[GraphNode], chunks: list[Chunk]) -> None:
        self.nodes = nodes
        self.chunks = {chunk.id: chunk for chunk in chunks}
        self.descriptions: dict[str, NodeDescription] = {}
        self.writes = 0

    def list_nodes(self, kinds: list[NodeKind] | None = None) -> list[GraphNode]:
        return [n for n in self.nodes if kinds is None or n.kind in kinds]

    def fetch_chunks(self, ids: list[str]) -> dict[str, Chunk]:
        return {i: self.chunks[i] for i in ids if i in self.chunks}

    def descriptions_for(self, node_ids: list[str]) -> dict[str, NodeDescription]:
        return {i: self.descriptions[i] for i in node_ids if i in self.descriptions}

    def upsert_descriptions(self, descriptions: list[NodeDescription]) -> None:
        self.writes += len(descriptions)
        for description in descriptions:
            self.descriptions[description.node_id] = description


def _fixture() -> tuple[_Store, FakeLLM]:
    chunks = [
        _chunk("c-code", ChunkKind.CODE, "int main(void) { sem_wait(&s); }", idx=3),
        _chunk("c-lecture", ChunkKind.LECTURE, "Semaphores on slide 12.", idx=2),
        _chunk("c-task", ChunkKind.TASK, "Write a timer with a semaphore.", idx=1),
        _chunk("c-tutorial", ChunkKind.TUTORIAL, "sem_post wakes one waiter.", idx=0),
    ]
    nodes = [
        GraphNode(
            id="api:sem_wait",
            kind=NodeKind.API_FUNCTION,
            label="sem_wait",
            chunk_ids=[c.id for c in chunks],
        ),
        GraphNode(id="concept:empty", kind=NodeKind.CONCEPT, label="empty", chunk_ids=[]),
        GraphNode(id="sop1/l4", kind=NodeKind.LAB, label="Lab 4", chunk_ids=["c-task"]),
    ]
    settings = Settings(llm_provider="fake", embedding_provider="fake")
    return _Store(nodes, chunks), FakeLLM(settings, canned="A semaphore counts permits.")


def test_sources_are_ranked_lab_text_first_and_code_last() -> None:
    store, _ = _fixture()
    kept = select_sources(list(store.chunks.values()))
    assert [c.id for c in kept] == ["c-task", "c-tutorial", "c-lecture", "c-code"]


def test_prompt_names_the_node_and_numbers_the_sources() -> None:
    store, _ = _fixture()
    node = store.nodes[0]
    prompt = build_user_prompt(node, select_sources(list(store.chunks.values())))
    assert prompt.startswith("sem_wait (api_function) appears in: sop1/l4.")
    assert "[1] sop1/l4 - s1" in prompt
    assert "[4] sop1/l4 - s3" in prompt


def test_describe_generates_once_then_reuses_the_cached_text() -> None:
    store, llm = _fixture()
    first = describe_nodes(store, llm)  # type: ignore[arg-type]
    assert (first.considered, first.generated, first.skipped_empty) == (2, 1, 1)
    assert store.descriptions["api:sem_wait"].text == "A semaphore counts permits."
    assert store.descriptions["api:sem_wait"].model == "fake/claude-opus-5"
    assert "sop1/l4" not in store.descriptions  # lab nodes are not described by default

    second = describe_nodes(store, llm)  # type: ignore[arg-type]
    assert (second.generated, second.skipped_unchanged) == (0, 1)
    assert store.writes == 1

    forced = describe_nodes(store, llm, force=True)  # type: ignore[arg-type]
    assert forced.generated == 1
    assert store.writes == 2


def test_hash_changes_with_the_sources_and_the_model() -> None:
    store, _ = _fixture()
    sources = select_sources(list(store.chunks.values()))
    base = source_hash(sources, "fake")
    assert source_hash(sources, "claude-opus-5") != base
    assert source_hash(sources[:-1], "fake") != base
    assert source_hash(list(reversed(sources)), "fake") == base


def test_kinds_and_limit_restrict_the_run() -> None:
    store, llm = _fixture()
    report = describe_nodes(store, llm, kinds=[NodeKind.LAB], limit=5)  # type: ignore[arg-type]
    assert (report.considered, report.generated) == (1, 1)
    assert "sop1/l4" in store.descriptions
