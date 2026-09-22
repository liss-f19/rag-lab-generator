"""
Role:   Unit tests for the hierarchical chunker: outline, parent links and oversized sections.
Input:  `settings`, `sample_lab` and `sample_documents` fixtures.
Output: Assertions; no side effects.
Flow:   Chunks the sample lab and checks section ids, breadcrumbs and task metadata, then repeats
        with a tiny chunk_size to exercise the semantic fallback split and the stage groups.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.models import ChunkKind, LabDocument
from rag_lab_generator.registry import create


def test_one_chunk_per_section(settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", "hierarchical", settings=settings).chunk(sample_lab)
    prose = [c for c in chunks if c.kind == ChunkKind.TUTORIAL]
    assert [c.section_id for c in prose] == [s.id for s in sample_lab.sections]


def test_parent_link_follows_section_tree(settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", "hierarchical", settings=settings).chunk(sample_lab)
    by_section = {c.section_id: c for c in chunks if c.kind == ChunkKind.TUTORIAL}
    child = by_section["reading-entry-metadata"]
    assert child.parent_id == by_section["browsing-a-directory"].id
    assert by_section["introduction"].parent_id is None


def test_breadcrumb_is_prepended_and_stored(settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", "hierarchical", settings=settings).chunk(sample_lab)
    child = next(c for c in chunks if c.section_id == "reading-entry-metadata")
    breadcrumb = "Lab 1: Filesystem API > Browsing a directory > Reading entry metadata"
    assert child.metadata["breadcrumb"] == breadcrumb
    assert child.text.startswith(breadcrumb)
    assert child.metadata["level"] == 3
    assert child.metadata["title"] == "Reading entry metadata"


def test_task_chunks_carry_metadata(settings: Settings, sample_lab: LabDocument) -> None:
    chunks = create("chunker", "hierarchical", settings=settings).chunk(sample_lab)
    tasks = [c for c in chunks if c.kind == ChunkKind.TASK]
    first = next(c for c in tasks if c.metadata["task_id"] == "example1")
    assert first.metadata["n_stages"] == 3
    assert "Stage 3:" in first.text


def test_task_chunks_carry_a_section_id(settings: Settings, sample_lab: LabDocument) -> None:
    """Task chunks must be addressable by section, like every other chunk of the strategy."""
    chunks = create("chunker", "hierarchical", settings=settings).chunk(sample_lab)
    tasks = [c for c in chunks if c.kind == ChunkKind.TASK]
    assert {c.section_id for c in tasks} == {"task:example1", "task:example2"}
    assert all(c.section_id == f"task:{c.metadata['task_id']}" for c in tasks)


def test_long_section_is_split_under_the_first_piece(
    settings: Settings, sample_lab: LabDocument
) -> None:
    tiny = settings.model_copy(update={"chunk_size": 120})
    chunks = create("chunker", "hierarchical", settings=tiny).chunk(sample_lab)
    pieces = [c for c in chunks if c.section_id == "browsing-a-directory"]
    assert len(pieces) > 1
    head = pieces[0]
    assert head.metadata["part"] == 0
    assert all(p.parent_id == head.id for p in pieces[1:])


def test_oversized_task_gets_stage_groups(settings: Settings, sample_lab: LabDocument) -> None:
    tiny = settings.model_copy(update={"chunk_size": 120})
    chunks = create("chunker", "hierarchical", settings=tiny).chunk(sample_lab)
    tasks = [c for c in chunks if c.kind == ChunkKind.TASK and c.metadata["task_id"] == "example1"]
    assert len(tasks) > 1
    assert tasks[0].parent_id is None
    assert all(c.parent_id == tasks[0].id for c in tasks[1:])
    assert all("stages" in c.metadata for c in tasks[1:])
    assert all(c.section_id == "task:example1" for c in tasks)
