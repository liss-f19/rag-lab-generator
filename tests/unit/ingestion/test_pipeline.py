"""
Role:   Unit tests of load_documents() against the tiny fixture corpus.
Input:  tests/fixtures/corpus/raw built by conftest's corpus_settings fixture.
Output: Assertions on document ids, kinds, lab ids and metadata; no network is used.
Flow:   Loads the fixture tree and checks that every expected document kind appears exactly once
        with the stable id other layers rely on.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.pipeline import load_documents
from rag_lab_generator.models import DocumentKind, LabDocument


def test_load_documents_returns_every_kind_of_the_fixture_tree(corpus_settings: Settings) -> None:
    documents = load_documents(corpus_settings, ["sop1"])
    by_id = {document.id: document for document in documents}
    assert set(by_id) == {
        "sop1/course/syllabus",
        "sop1/lecture/w2/index",
        "sop1/lecture/w2/slides",
        "sop1/lecture/w2/OPS1_Fixture",
        "sop1/lecture/w2/code/demo.c",
        "sop1/l1",
        "sop1/l1/summary",
        "external/kozlowski/unix/06-files",
        "external/kozlowski/unix/bash1",
        "external/kozlowski/unix/09-vim",
    }
    assert by_id["sop1/lecture/w2/OPS1_Fixture"].kind is DocumentKind.LECTURE_PDF
    assert len(by_id["sop1/lecture/w2/OPS1_Fixture"].sections) == 2
    assert by_id["sop1/lecture/w2/code/demo.c"].kind is DocumentKind.LECTURE_CODE
    assert by_id["sop1/lecture/w2/slides"].kind is DocumentKind.LECTURE_SLIDES
    assert by_id["sop1/course/syllabus"].kind is DocumentKind.COURSE_INFO


def test_ids_are_unique_and_documents_carry_their_lab(corpus_settings: Settings) -> None:
    documents = load_documents(corpus_settings, ["sop1"])
    assert len({document.id for document in documents}) == len(documents)
    assert documents and all(document.course.value == "sop1" for document in documents)
    external = next(d for d in documents if d.id == "external/kozlowski/unix/06-files")
    assert external.kind is DocumentKind.EXTERNAL_PDF
    assert external.lab_id == "sop1/l1"
    summary = next(d for d in documents if d.kind is DocumentKind.SUMMARY)
    assert summary.lab_id == "sop1/l1"


def test_lab_document_is_rebuilt_with_its_code_and_metadata(corpus_settings: Settings) -> None:
    lab = next(d for d in load_documents(corpus_settings, ["sop1"]) if isinstance(d, LabDocument))
    assert lab.id == "sop1/l1"
    assert lab.slug == "l1_filesystem"
    assert lab.tasks[0].stages[1].text == "Print sizes."
    assert lab.code_files[0].content.startswith("#include")
    assert lab.metadata["n_tasks"] == 1
    assert lab.metadata["topics"] == ["opendir", "readdir", "S_ISDIR"]


def test_course_wide_material_has_no_lab_and_shell_scripts_become_documents(
    corpus_settings: Settings,
) -> None:
    by_id = {d.id: d for d in load_documents(corpus_settings, ["sop1"])}
    course_wide = by_id["external/kozlowski/unix/09-vim"]
    assert course_wide.kind is DocumentKind.EXTERNAL_PDF
    assert course_wide.lab_id is None

    script = by_id["external/kozlowski/unix/bash1"]
    assert script.lab_id == "sop1/l1"
    assert script.metadata["format"] == "sh"
    assert script.sections[0].text.startswith("```bash")


def test_support_metadata_separates_background_from_primary(corpus_settings: Settings) -> None:
    for document in load_documents(corpus_settings, ["sop1"]):
        expected = "background" if document.kind is DocumentKind.EXTERNAL_PDF else "primary"
        assert document.metadata["support"] == expected


def test_unknown_course_directory_is_ignored(corpus_settings: Settings) -> None:
    assert load_documents(corpus_settings, ["sop2"]) == []
