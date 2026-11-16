from pathlib import Path

import pytest

from rag_lab_generator.domain.errors import (
    ExtractionError,
    UnsupportedDocumentFormatError,
)
from rag_lab_generator.ingestion.extractors import (
    HTML,
    MARKDOWN,
    PDF,
    PLAIN_TEXT,
    HtmlExtractor,
    MarkdownExtractor,
    PdfExtractor,
    PlainTextExtractor,
    check_signature,
    extractor_for,
    media_type_for,
    normalize_text,
)
from tests.fakes import make_pdf

DATASET = Path(__file__).resolve().parents[2] / "dataset"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("lecture.md", MARKDOWN),
        ("Notes.MARKDOWN", MARKDOWN),
        ("readme.txt", PLAIN_TEXT),
        ("page.htm", HTML),
        ("page.html", HTML),
        ("slides.PDF", PDF),
    ],
)
def test_media_type_is_derived_from_the_extension(filename: str, expected: str) -> None:
    assert media_type_for(filename) == expected


def test_unsupported_extension_lists_accepted_formats() -> None:
    with pytest.raises(UnsupportedDocumentFormatError) as error:
        media_type_for("lab.docx")
    assert error.value.details["accepted_formats"] == ["pdf", "html", "txt", "md"]


def test_extractor_for_unknown_media_type_is_rejected() -> None:
    with pytest.raises(UnsupportedDocumentFormatError):
        extractor_for("application/msword")


def test_pdf_signature_is_checked() -> None:
    check_signature(PDF, b"%PDF-1.7 ...")
    check_signature(MARKDOWN, b"# not checked")
    with pytest.raises(UnsupportedDocumentFormatError):
        check_signature(PDF, b"<html>not a pdf</html>")


def test_normalize_text_unifies_newlines_and_blank_lines() -> None:
    assert normalize_text("a  \r\nb\r\n\r\n\r\n\r\nc\x00\n\n") == "a\nb\n\nc"


def test_markdown_sections_follow_the_heading_hierarchy() -> None:
    source = b"""# L4 Tutorial: Synchronization
Intro text.

## Mutex
Lock before use.

### Example
Code follows.

## Barrier
Wait for all threads.
"""
    blocks = MarkdownExtractor().extract(source)
    assert [(block.section_path, block.text) for block in blocks] == [
        (("L4 Tutorial: Synchronization",), "Intro text."),
        (("L4 Tutorial: Synchronization", "Mutex"), "Lock before use."),
        (("L4 Tutorial: Synchronization", "Mutex", "Example"), "Code follows."),
        (("L4 Tutorial: Synchronization", "Barrier"), "Wait for all threads."),
    ]


def test_markdown_headings_inside_code_fences_are_kept_as_code() -> None:
    source = b"""## Build
```makefile
# not a heading
all: prog
```
After the code.
"""
    blocks = MarkdownExtractor().extract(source)
    assert len(blocks) == 1
    assert blocks[0].section_path == ("Build",)
    assert "# not a heading" in blocks[0].text
    assert blocks[0].text.endswith("After the code.")


def test_markdown_heading_emphasis_is_removed() -> None:
    blocks = MarkdownExtractor().extract(b"## **Stage 1** (3 p.)\ntext")
    assert blocks[0].section_path == ("Stage 1 (3 p.)",)


def test_markdown_extracts_a_real_course_document() -> None:
    blocks = MarkdownExtractor().extract(
        (DATASET / "L4_Sample_Task_3_Thread_Pool.md").read_bytes()
    )
    paths = {block.section_path for block in blocks}
    assert ("L4 Sample Task 3: Thread Pool", "Stages", "Stage 1") in {
        path[:3] for path in paths
    }
    assert any("work_function" in block.text for block in blocks)


def test_plain_text_is_one_block_and_rejects_invalid_utf8() -> None:
    assert PlainTextExtractor().extract("Zażółć gęślą jaźń\n".encode()) == [
        PlainTextExtractor().extract("Zażółć gęślą jaźń".encode())[0]
    ]
    assert not PlainTextExtractor().extract(b"   \n\n")
    with pytest.raises(ExtractionError) as error:
        PlainTextExtractor().extract(b"\xff\xfe\xfa broken")
    assert "UTF-8" in error.value.message


def test_html_text_is_grouped_by_headings_without_scripts() -> None:
    source = b"""<html><head><title>T</title><style>p{}</style></head><body>
<h1>Operating   Systems</h1><p>Course   intro.</p>
<script>var hidden = 1;</script>
<h2>Pipes</h2><p>Use <b>pipe()</b> and<br>close ends.</p>
<pre>int fd[2];
    pipe(fd);</pre>
<ul><li>first</li><li>second</li></ul>
</body></html>"""
    blocks = HtmlExtractor().extract(source)
    assert blocks[0].section_path == ("Operating Systems",)
    assert blocks[0].text == "Course intro."
    pipes = blocks[1]
    assert pipes.section_path == ("Operating Systems", "Pipes")
    assert "Use pipe() and\nclose ends." in pipes.text
    assert "int fd[2];\n    pipe(fd);" in pipes.text
    assert "first\n\nsecond" in pipes.text
    assert all("hidden" not in block.text for block in blocks)


def test_pdf_text_keeps_page_numbers() -> None:
    data = make_pdf(["Semaphores and mutexes", "", "Condition variables"])
    blocks = PdfExtractor().extract(data)
    assert [(block.page_number, block.text) for block in blocks] == [
        (1, "Semaphores and mutexes"),
        (3, "Condition variables"),
    ]


def test_damaged_pdf_raises_an_actionable_error() -> None:
    with pytest.raises(ExtractionError):
        PdfExtractor().extract(b"%PDF-1.4\nthis is not really a pdf")
