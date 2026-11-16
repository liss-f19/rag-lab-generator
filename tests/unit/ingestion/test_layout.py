"""
Role:   Unit tests of layout.py: zip attachment unpacking and lab directory building.
Input:  Temporary zip archives and a minimal LabDocument built in the test.
Output: Assertions on the unpacked files, their CodeFile refs, lab.xml and manifest.json.
Flow:   Builds an archive with sources, a Makefile, a binary and a pdf, unpacks it, then runs
        build_lab with the archive as the only attachment and reads the written lab back.
"""

import zipfile
from pathlib import Path

from rag_lab_generator.ingestion import layout
from rag_lab_generator.ingestion.lab_xml import read_lab_xml
from rag_lab_generator.models import CodeFile, Course, LabDocument, LabManifest, Task

ARCHIVE_URL = "https://sop.mini.pw.edu.pl/files/sop1l4e2.zip"


def _write_archive(path: Path, top_level: str = "src/") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(
            f"{top_level}sop-mss.c", "#include <stdio.h>\nint main(void) { return 0; }\n"
        )
        bundle.writestr(f"{top_level}Makefile", "all:\n\tgcc sop-mss.c\n")
        bundle.writestr(f"{top_level}ops-printer", b"\x7fELF\x00\x00binary")
        bundle.writestr(f"{top_level}notes.pdf", b"%PDF-1.4 text")
        bundle.writestr(f"{top_level}../escape.c", "int x;\n")
    return path


def test_unpack_attachment_keeps_text_sources_and_drops_the_top_level_dir(tmp_path: Path) -> None:
    archive = _write_archive(tmp_path / "sop1l4e2.zip")
    lab_dir = tmp_path / "lab"

    unpacked = layout.unpack_attachment(archive, lab_dir, ARCHIVE_URL)

    assert [c.ref for c in unpacked] == ["src/sop1l4e2/Makefile", "src/sop1l4e2/sop-mss.c"]
    assert {c.lang for c in unpacked} == {"make", "c"}
    assert all(c.source_url == ARCHIVE_URL for c in unpacked)
    assert (lab_dir / "src/sop1l4e2/sop-mss.c").read_text().startswith("#include")
    assert not (lab_dir / "src/sop1l4e2/ops-printer").exists()
    assert not (lab_dir / "src/sop1l4e2/notes.pdf").exists()
    assert not (lab_dir / "src/escape.c").exists()


def test_unpack_attachment_keeps_paths_without_a_common_top_level(tmp_path: Path) -> None:
    archive = _write_archive(tmp_path / "flat.zip", top_level="")

    unpacked = layout.unpack_attachment(archive, tmp_path / "lab", None)

    assert [c.ref for c in unpacked] == ["src/flat/Makefile", "src/flat/sop-mss.c"]


def test_build_lab_registers_unpacked_files_in_lab_xml_and_manifest(tmp_path: Path) -> None:
    archive = _write_archive(tmp_path / "static" / "sop1l4e2.zip")
    lab = LabDocument(
        id="sop1/l4",
        course=Course.SOP1,
        title="Synchronization",
        number="4",
        slug="l4_synchronization",
        tasks=[
            Task(id="example2", title="E2", statement="Do it.", attachments=["src/sop1l4e2.zip"])
        ],
        code_files=[
            CodeFile(ref="src/prog21.c", lang="c", content="int main(void) { return 0; }\n"),
            CodeFile(ref="src/sop1l4e2.zip", lang="zip", content="", source_url=ARCHIVE_URL),
        ],
    )
    raw_dir = tmp_path / "raw"

    manifest = layout.build_lab(
        lab, raw_dir, {archive.name: archive}, tmp_path / "external", layout.LabMapping()
    )

    lab_dir = raw_dir / "sop1" / "l4_synchronization"
    assert manifest.src == ["prog21.c", "sop1l4e2.zip", "sop1l4e2/Makefile", "sop1l4e2/sop-mss.c"]
    assert {Path(s.local_path).name for s in manifest.sources} >= {"Makefile", "sop-mss.c"}
    reread = LabManifest.model_validate_json((lab_dir / "manifest.json").read_text())
    assert reread.src == manifest.src

    loaded = read_lab_xml(lab_dir / "lab.xml")
    by_ref = {c.ref: c for c in loaded.code_files}
    assert set(by_ref) == {
        "src/prog21.c",
        "src/sop1l4e2.zip",
        "src/sop1l4e2/Makefile",
        "src/sop1l4e2/sop-mss.c",
    }
    assert by_ref["src/sop1l4e2/sop-mss.c"].content.startswith("#include")
    assert by_ref["src/sop1l4e2/sop-mss.c"].source_url == ARCHIVE_URL
    assert by_ref["src/sop1l4e2.zip"].content == ""
    assert loaded.tasks[0].attachments == ["src/sop1l4e2.zip"]
