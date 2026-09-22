"""
Role:   Unit tests of the lab.xml writer, reader and schema validation.
Input:  A LabDocument built in the test and the fixture lab.xml.
Output: Assertions that the round trip is lossless and that invalid trees are rejected.
Flow:   Writes a lab, reads it back with its src/ contents and compares the models field by
        field; then removes a required attribute and expects LabXmlError.
"""

from pathlib import Path

import pytest
from lxml import etree

from rag_lab_generator.ingestion.lab_xml import (
    LabXmlError,
    build_tree,
    read_lab_xml,
    validate,
    write_lab_xml,
)
from rag_lab_generator.models import CodeFile, Course, LabDocument, Reference, Section, Stage, Task


def make_lab() -> LabDocument:
    return LabDocument(
        id="sop1/l1",
        course=Course.SOP1,
        title="Filesystem",
        number="1",
        slug="l1_filesystem",
        source_url="https://sop.mini.pw.edu.pl/en/sop1/lab/l1/",
        topics=["opendir", "S_ISDIR"],
        sections=[
            Section(
                id="browsing",
                title="Browsing a directory",
                level=2,
                order=0,
                text="Use `opendir`.\n\n```c\nint main(void);\n```",
                code_refs=["src/demo.c"],
            ),
            Section(id="notes", title="Notes", level=3, order=1, text="x", parent_id="browsing"),
        ],
        tasks=[
            Task(
                id="example1",
                title="Example task 1",
                statement="Write a program using <stdio.h> & friends.",
                stages=[Stage(n=1, text="Open it."), Stage(n=2, text="Close it.")],
                solution_refs=["src/demo.c"],
                attachments=["src/fixture.zip"],
                notes="An answer.",
                source_url="https://sop.mini.pw.edu.pl/en/sop1/lab/l1/example1/",
            )
        ],
        code_files=[
            CodeFile(ref="src/demo.c", lang="c", content="int main(void);\n", source_url="u")
        ],
        references=[Reference(url="https://man7.org/", title="man pages")],
        metadata={"origin": "unit-test"},
    )


def test_round_trip_is_lossless(tmp_path: Path) -> None:
    lab = make_lab()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.c").write_text("int main(void);\n", encoding="utf-8")
    write_lab_xml(lab, tmp_path / "lab.xml")
    assert read_lab_xml(tmp_path / "lab.xml") == lab


def test_written_file_validates_against_the_schema(tmp_path: Path) -> None:
    write_lab_xml(make_lab(), tmp_path / "lab.xml")
    validate(etree.parse(str(tmp_path / "lab.xml")).getroot())


def test_missing_required_attribute_is_rejected() -> None:
    root = build_tree(make_lab())
    del root.attrib["slug"]
    with pytest.raises(LabXmlError):
        validate(root)


def test_fixture_lab_xml_is_readable(fixtures_dir: Path) -> None:
    lab = read_lab_xml(fixtures_dir / "corpus/raw/sop1/l1_filesystem/lab.xml")
    assert lab.id == "sop1/l1"
    assert lab.topics == ["opendir", "readdir", "S_ISDIR"]
    assert lab.code_files[0].content.startswith("#include")
