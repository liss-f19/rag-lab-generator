"""
Role:   Unit tests of the per-document grouping shown under a node description.
Input:  Hand-built chunks of a lab, its summary and a lecture pdf plus their DocumentHeaders.
Output: Assertions on the group order, the corpus slug and the location labels.
Flow:   Groups a mixed chunk list and checks that the lab comes first with its slug, that a
        lecture page, a task, a code file and a multi-part section are labelled readably, and
        that a chunk without a stored document still forms a group.
"""

from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    DocumentHeader,
    DocumentKind,
)
from rag_lab_generator.retrieval.graph.sources import group_sources, location_label


def _chunk(
    chunk_id: str,
    document_id: str,
    kind: ChunkKind,
    idx: int,
    section_id: str | None = None,
    **metadata: object,
) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        course=Course.SOP2,
        lab_id="sop2/l5" if document_id.startswith("sop2/l5") else None,
        kind=kind,
        strategy="hierarchical",
        idx=idx,
        text="x",
        section_id=section_id,
        metadata=dict(metadata),
    )


HEADERS = {
    "sop2/l5": DocumentHeader(
        id="sop2/l5",
        course=Course.SOP2,
        kind=DocumentKind.LAB,
        lab_id="sop2/l5",
        title="FIFO/pipe",
        metadata={"slug": "l5_fifo_pipe"},
    ),
    "sop2/lecture/pipes/POSIX-pipes": DocumentHeader(
        id="sop2/lecture/pipes/POSIX-pipes",
        course=Course.SOP2,
        kind=DocumentKind.LECTURE_PDF,
        title="POSIX-pipes",
        metadata={"topic": "pipes"},
    ),
}


def test_groups_are_labs_first_with_slug_and_readable_locations() -> None:
    chunks = [
        _chunk("l20", "sop2/lecture/pipes/POSIX-pipes", ChunkKind.LECTURE, 20, "page-20"),
        _chunk("l3", "sop2/lecture/pipes/POSIX-pipes", ChunkKind.LECTURE, 3, "page-3"),
        _chunk("t1", "sop2/l5", ChunkKind.TASK, 40, "task:example1", title="Task 1 - FIFO"),
        _chunk(
            "s3",
            "sop2/l5",
            ChunkKind.TUTORIAL,
            7,
            "stage-3",
            breadcrumb="FIFO/pipe > Task 1 - FIFO > Stage 3",
            part=1,
            n_parts=2,
        ),
        _chunk("code", "sop2/l5", ChunkKind.CODE, 50, ref="src/prog21.c"),
        _chunk("orphan", "external/kozlowski/unix/06-files", ChunkKind.LECTURE, 11, "page-11"),
    ]
    groups = group_sources(chunks, HEADERS)
    # same document kind (lecture pdf) for the last two, so they follow title order
    assert [g.document_id for g in groups] == [
        "sop2/l5",
        "external/kozlowski/unix/06-files",
        "sop2/lecture/pipes/POSIX-pipes",
    ]
    lab = groups[0]
    assert lab.slug == "l5_fifo_pipe" and lab.title == "FIFO/pipe" and lab.kind is DocumentKind.LAB
    assert [loc.label for loc in lab.locations] == [
        "Task 1 - FIFO > Stage 3 (part 2/2)",
        "Task: Task 1 - FIFO",
        "src/prog21.c",
    ]
    lecture = groups[2]
    assert lecture.slug is None
    assert [loc.label for loc in lecture.locations] == ["page 3", "page 20"]
    orphan = groups[1]
    assert orphan.title == "external/kozlowski/unix/06-files"
    assert orphan.kind is DocumentKind.LECTURE_PDF


def test_location_label_falls_back_to_the_section_or_index() -> None:
    assert location_label(_chunk("a", "d", ChunkKind.INFO, 4, "rules")) == "rules"
    assert location_label(_chunk("b", "d", ChunkKind.SUMMARY, 4)) == "chunk 4"
    assert location_label(_chunk("c", "d", ChunkKind.TUTORIAL, 1, "x", breadcrumb="Only")) == "Only"
