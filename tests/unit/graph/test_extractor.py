"""
Role:   Unit tests for the deterministic knowledge-graph extractor.
Input:  The shared sample corpus plus small purpose-built document sets.
Output: Assertions on node ids/kinds, edge kinds, api and concept detection and chunk attachment.
Flow:   Runs extract_graph on the fixtures and inspects the returned nodes and edges.
"""

from rag_lab_generator.models import (
    Chunk,
    CodeFile,
    Course,
    Document,
    DocumentKind,
    EdgeKind,
    LabDocument,
    NodeKind,
    Section,
    Task,
)
from rag_lab_generator.retrieval.graph.extractor import extract_graph

LAB_ID = "sop1/lab/l1_filesystem"


def _index(nodes: list) -> dict:
    return {n.id: n for n in nodes}


def _edge_set(edges: list) -> set:
    return {(e.src, e.dst, e.kind) for e in edges}


def test_core_nodes_and_contains_chain(
    sample_documents: list[Document], sample_chunks: list[Chunk]
) -> None:
    nodes, edges = extract_graph(sample_documents, sample_chunks)
    by_id = _index(nodes)
    assert by_id["course:sop1"].kind is NodeKind.COURSE
    assert by_id[LAB_ID].kind is NodeKind.LAB
    assert by_id[LAB_ID].properties["number"] == "1"
    assert by_id[f"{LAB_ID}#section:introduction"].kind is NodeKind.SECTION
    assert by_id[f"{LAB_ID}#task:example1"].kind is NodeKind.TASK
    assert by_id[f"{LAB_ID}#code:src/prog1.c"].kind is NodeKind.CODE_FILE
    assert by_id["sop1/lecture/w2/filesystem"].kind is NodeKind.LECTURE
    assert by_id["sop1/info/rules"].kind is NodeKind.LECTURE
    links = _edge_set(edges)
    assert ("course:sop1", LAB_ID, EdgeKind.CONTAINS) in links
    assert (LAB_ID, f"{LAB_ID}#section:introduction", EdgeKind.CONTAINS) in links
    assert (LAB_ID, f"{LAB_ID}#task:example1", EdgeKind.CONTAINS) in links


def test_section_parent_and_code_edges(
    sample_documents: list[Document], sample_chunks: list[Chunk]
) -> None:
    _, edges = extract_graph(sample_documents, sample_chunks)
    links = _edge_set(edges)
    parent = f"{LAB_ID}#section:browsing-a-directory"
    child = f"{LAB_ID}#section:reading-entry-metadata"
    assert (parent, child, EdgeKind.CONTAINS) in links
    assert (parent, f"{LAB_ID}#code:src/prog1.c", EdgeKind.RELATED_TO) in links
    assert (f"{LAB_ID}#task:example1", f"{LAB_ID}#code:src/prog1.c", EdgeKind.SOLVED_BY) in links


def test_chunk_attachment(sample_documents: list[Document], sample_chunks: list[Chunk]) -> None:
    nodes, _ = extract_graph(sample_documents, sample_chunks)
    by_id = _index(nodes)
    section = by_id[f"{LAB_ID}#section:browsing-a-directory"]
    assert f"hierarchical:{LAB_ID}:1" in section.chunk_ids
    # the same section chunked by another strategy is attached too, filtering happens at query time
    assert f"fixed:{LAB_ID}:0" in section.chunk_ids
    assert f"hierarchical:{LAB_ID}:4" in by_id[f"{LAB_ID}#task:example1"].chunk_ids
    assert f"hierarchical:{LAB_ID}:6" in by_id[f"{LAB_ID}#code:src/prog1.c"].chunk_ids
    assert by_id["api:opendir"].chunk_ids
    # the lab keeps only the chunks no finer node claims
    assert by_id[LAB_ID].chunk_ids == [f"hierarchical:{LAB_ID}:99"]


def test_api_nodes_from_topics(
    sample_documents: list[Document], sample_chunks: list[Chunk]
) -> None:
    nodes, edges = extract_graph(sample_documents, sample_chunks)
    by_id = _index(nodes)
    for topic in ("opendir", "readdir", "stat"):
        assert by_id[f"api:{topic}"].kind is NodeKind.API_FUNCTION
        assert by_id[f"api:{topic}"].label == topic
    links = _edge_set(edges)
    assert (LAB_ID, "api:opendir", EdgeKind.USES_API) in links
    assert (
        f"{LAB_ID}#section:browsing-a-directory",
        "api:opendir",
        EdgeKind.USES_API,
    ) in links


def test_api_needs_code_evidence() -> None:
    """Only identifiers real code calls (or a lab declares) may become api nodes."""
    lab = LabDocument(
        id="sop1/lab/l2_signals",
        course=Course.SOP1,
        kind=DocumentKind.LAB,
        title="Lab 2",
        number="2",
        slug="l2_signals",
        lab_id="sop1/lab/l2_signals",
        sections=[
            Section(
                id="a",
                title="A",
                order=0,
                text=(
                    "Install the handler as shown on the page (see the manual).\n\n"
                    "```c\n"
                    'if (x) { printf("a"); }\n'
                    "while (y) { sigaction(SIGINT, &sa, NULL); }\n"
                    "```\n"
                ),
            ),
            Section(
                id="b",
                title="B",
                order=1,
                text="Call sigaction (twice) and check sizeof(struct sigaction).",
            ),
            Section(id="c", title="C", order=2, text="mq_open(name, O_RDONLY) is only prose here"),
        ],
    )
    nodes, _ = extract_graph([lab], [])
    ids = {n.id for n in nodes}
    # called inside the fenced block, so the prose mention in section b is trusted too
    assert "api:sigaction" in ids
    for banned in ("api:printf", "api:if", "api:while", "api:sizeof"):
        assert banned not in ids
    # prose-only parentheses never create a node, whatever the word is
    assert "api:page" not in ids
    assert "api:mq_open" not in ids


def test_code_file_and_inline_span_are_evidence() -> None:
    lab = LabDocument(
        id="sop1/lab/l3_io",
        course=Course.SOP1,
        kind=DocumentKind.LAB,
        title="Lab 3",
        number="3",
        slug="l3_io",
        lab_id="sop1/lab/l3_io",
        sections=[
            Section(
                id="a",
                title="A",
                order=0,
                text="Use `mq_open(name, flags)` and then call mq_send(...) on the queue.",
            ),
            Section(id="b", title="B", order=1, text="Later the program calls mq_unlink(name)."),
        ],
        code_files=[CodeFile(ref="src/q.c", lang="c", content="int r = mq_unlink(name);\n")],
    )
    nodes, _ = extract_graph([lab], [])
    ids = {n.id for n in nodes}
    # inline code span is code evidence
    assert "api:mq_open" in ids
    # CodeFile content is code evidence
    assert "api:mq_unlink" in ids
    # mentioned only in prose, never called in code
    assert "api:mq_send" not in ids


def test_lab_topics_bypass_code_evidence() -> None:
    lab = _mini_lab("sop1/lab/l1_fs", "l1_fs", Course.SOP1, ["opendir", "readdir"])
    nodes, _ = extract_graph([lab], [])
    ids = {n.id for n in nodes}
    assert "api:opendir" in ids
    assert "api:readdir" in ids


def test_concept_detection(sample_documents: list[Document], sample_chunks: list[Chunk]) -> None:
    nodes, edges = extract_graph(sample_documents, sample_chunks)
    by_id = _index(nodes)
    assert by_id["concept:inode"].kind is NodeKind.CONCEPT
    assert by_id["concept:directory entry"].label == "directory entry"
    assert "concept:symbolic link" in by_id
    assert "concept:errno" in by_id
    links = _edge_set(edges)
    assert (
        "sop1/lecture/w2/filesystem",
        "concept:inode",
        EdgeKind.COVERS_CONCEPT,
    ) in links
    assert (
        f"{LAB_ID}#section:error-handling",
        "concept:errno",
        EdgeKind.COVERS_CONCEPT,
    ) in links


def _mini_lab(lab_id: str, slug: str, course: Course, topics: list[str]) -> LabDocument:
    return LabDocument(
        id=lab_id,
        course=course,
        kind=DocumentKind.LAB,
        title=lab_id,
        number=slug,
        slug=slug,
        lab_id=lab_id,
        topics=topics,
        sections=[
            Section(
                id="body",
                title="Body",
                order=0,
                text="A pipe and a socket and a mutex are used with " + " ".join(topics),
            )
        ],
    )


def test_prerequisite_chain_across_courses() -> None:
    labs = [
        _mini_lab("sop1/lab/l4_threads", "l4_threads", Course.SOP1, []),
        _mini_lab("sop2/lab/l5_5_shm", "l5_5_shm", Course.SOP2, []),
        _mini_lab("sop1/lab/l1_fs", "l1_fs", Course.SOP1, []),
        _mini_lab("sop2/lab/l5_sockets", "l5_sockets", Course.SOP2, []),
    ]
    _, edges = extract_graph(list(labs), [])
    chain = [(e.src, e.dst) for e in edges if e.kind is EdgeKind.PREREQUISITE_OF]
    assert chain == [
        ("sop1/lab/l1_fs", "sop1/lab/l4_threads"),
        ("sop1/lab/l4_threads", "sop2/lab/l5_sockets"),
        ("sop2/lab/l5_sockets", "sop2/lab/l5_5_shm"),
    ]


def test_related_to_uses_jaccard() -> None:
    labs = [
        _mini_lab("sop1/lab/l1_fs", "l1_fs", Course.SOP1, ["opendir", "readdir"]),
        _mini_lab("sop1/lab/l2_fs", "l2_fs", Course.SOP1, ["opendir", "readdir"]),
    ]
    _, edges = extract_graph(list(labs), [])
    related = [
        e for e in edges if e.kind is EdgeKind.RELATED_TO and e.src.startswith("sop1/lab/l1")
    ]
    assert related and related[0].dst == "sop1/lab/l2_fs"
    assert related[0].weight == 1.0


def test_covered_by_lecture_and_summary() -> None:
    lab = _mini_lab("sop1/lab/l1_fs", "l1_fs", Course.SOP1, ["opendir"])
    summary = Document(
        id="sop1/lab/l1_fs/summary",
        course=Course.SOP1,
        kind=DocumentKind.SUMMARY,
        title="Summary of lab 1",
        lab_id="sop1/lab/l1_fs",
        sections=[Section(id="s", title="S", order=0, text="Directories and inodes.")],
    )
    _, edges = extract_graph([lab, summary], [])
    assert (lab.id, summary.id, EdgeKind.COVERED_BY_LECTURE) in _edge_set(edges)


def test_ids_and_order_are_stable(
    sample_documents: list[Document], sample_chunks: list[Chunk]
) -> None:
    first_nodes, first_edges = extract_graph(sample_documents, sample_chunks)
    second_nodes, second_edges = extract_graph(list(reversed(sample_documents)), sample_chunks)
    assert [n.id for n in first_nodes] == [n.id for n in second_nodes]
    assert [(e.src, e.dst, e.kind) for e in first_edges] == [
        (e.src, e.dst, e.kind) for e in second_edges
    ]
    assert first_nodes == sorted(first_nodes, key=lambda n: n.id)


def test_task_text_feeds_detection() -> None:
    lab = LabDocument(
        id="sop2/lab/l6_threads",
        course=Course.SOP2,
        kind=DocumentKind.LAB,
        title="Lab 6",
        number="6",
        slug="l6_threads",
        lab_id="sop2/lab/l6_threads",
        sections=[
            Section(
                id="a",
                title="A",
                order=0,
                text=(
                    "Threads are started with\n\n"
                    "```c\npthread_create(&t, NULL, worker, NULL);\n```\n"
                ),
            )
        ],
        tasks=[
            Task(
                id="example1",
                title="Worker pool",
                statement="Spawn workers with pthread_create(&t, NULL, worker, NULL).",
            )
        ],
    )
    nodes, edges = extract_graph([lab], [])
    assert "api:pthread_create" in {n.id for n in nodes}
    assert (
        "sop2/lab/l6_threads#task:example1",
        "api:pthread_create",
        EdgeKind.USES_API,
    ) in _edge_set(edges)


def test_task_is_related_to_the_code_unpacked_from_its_attachment() -> None:
    lab = LabDocument(
        id="sop1/lab/l4",
        course=Course.SOP1,
        kind=DocumentKind.LAB,
        title="Lab 4",
        number="4",
        slug="l4_synchronization",
        lab_id="sop1/lab/l4",
        tasks=[
            Task(id="example2", title="E2", statement="Finish it.", attachments=["src/e2.zip"]),
            Task(id="example3", title="E3", statement="Other.", attachments=[]),
        ],
        code_files=[
            CodeFile(ref="src/e2.zip", lang="zip", content=""),
            CodeFile(ref="src/e2/Makefile", lang="make", content="all:\n"),
            CodeFile(ref="src/e2/sop-mss.c", lang="c", content="int main(void) { return 0; }"),
            CodeFile(ref="src/prog21.c", lang="c", content="int main(void) { return 1; }"),
        ],
    )
    _, edges = extract_graph([lab], [])
    links = _edge_set(edges)
    task = "sop1/lab/l4#task:example2"
    assert (task, "sop1/lab/l4#code:src/e2/Makefile", EdgeKind.RELATED_TO) in links
    assert (task, "sop1/lab/l4#code:src/e2/sop-mss.c", EdgeKind.RELATED_TO) in links
    assert (task, "sop1/lab/l4#code:src/e2.zip", EdgeKind.RELATED_TO) not in links
    assert (task, "sop1/lab/l4#code:src/prog21.c", EdgeKind.RELATED_TO) not in links
    assert not any(
        src == "sop1/lab/l4#task:example3" and kind is EdgeKind.RELATED_TO for src, _, kind in links
    )
