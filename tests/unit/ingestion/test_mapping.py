"""
Role:   Unit tests of the packaged mapping.yaml and the layout helpers that read it.
Input:  rag_lab_generator/ingestion/mapping.yaml and the LAB_SLUGS table.
Output: Assertions that every lab is mapped and every entry is syntactically valid.
Flow:   Loads the mapping, checks that its keys are exactly the known lab ids and that every
        lecture entry is "<course>/<topic>" and every external entry "unix/..." or "tcpip/...".
"""

import re

from rag_lab_generator.ingestion.layout import load_course_mapping, load_mapping
from rag_lab_generator.ingestion.parsers.hugo_markdown import LAB_SLUGS

LECTURE_RE = re.compile(r"^sop[12]/[a-z0-9_.]+$")
EXTERNAL_RE = re.compile(r"^(unix|tcpip)/[A-Za-z0-9_.-]+\.(pdf|sh|txt)$")

# Every file the kozlowski source downloads from the unix directory.
UNIX_FILES: tuple[str, ...] = (
    "00-basics.pdf",
    "01-lab-unix.pdf",
    "01-unix.pdf",
    "02-bash.pdf",
    "02-lab-bash.pdf",
    "03-commands.pdf",
    "03-lab-commands.pdf",
    "04-lab-streams.pdf",
    "04-streams.pdf",
    "05-lab-users.pdf",
    "05-users.pdf",
    "06-files.pdf",
    "06-lab-files.pdf",
    "07-lab-processes.pdf",
    "07-processes.pdf",
    "08-lab-system.pdf",
    "08-system.pdf",
    "09-vim.pdf",
    "10-awk.pdf",
    "11-lab-bash.pdf",
    "awk-man-b5-1.pdf",
    "bash1.sh",
    "bash2.sh",
    "bash3.sh",
    "bash4.sh",
    "tutorial.gcc_make.txt",
)


def test_every_lab_is_mapped() -> None:
    mapping = load_mapping()
    assert set(mapping) == set(LAB_SLUGS)


def test_lecture_entries_are_course_qualified_topics() -> None:
    for lab_id, entry in load_mapping().items():
        for topic in entry.lectures:
            assert LECTURE_RE.match(topic), f"{lab_id}: bad lecture entry {topic!r}"


def test_external_entries_name_a_known_directory_and_suffix() -> None:
    for lab_id, entry in load_mapping().items():
        for name in entry.kozlowski:
            assert EXTERNAL_RE.match(name), f"{lab_id}: bad external entry {name!r}"


def test_socket_labs_get_the_transport_layer_lectures() -> None:
    mapping = load_mapping()
    assert "tcpip/lecture_4.pdf" in mapping["sop2/l7"].kozlowski
    assert "tcpip/lecture_4.pdf" in mapping["sop2/l8"].kozlowski
    assert "sop2/sockets" in mapping["sop2/l7"].lectures


def test_course_wide_material_is_mapped_for_sop1() -> None:
    courses = load_course_mapping()
    assert set(courses) == {"sop1", "sop2"}
    assert courses["sop1"].kozlowski == [
        "unix/09-vim.pdf",
        "unix/10-awk.pdf",
        "unix/awk-man-b5-1.pdf",
    ]


def test_every_downloaded_unix_file_is_mapped_somewhere() -> None:
    mapped = {name for entry in load_mapping().values() for name in entry.kozlowski}
    mapped |= {name for entry in load_course_mapping().values() for name in entry.kozlowski}
    for name in UNIX_FILES:
        assert f"unix/{name}" in mapped, f"{name} is downloaded but never mapped"
