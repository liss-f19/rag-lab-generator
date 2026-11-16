"""
Role:   Unit tests of the reveal.js deck parser.
Input:  tests/fixtures/slides.md.
Output: Assertions on the produced Sections.
Flow:   Parses the fixture deck and checks the slide count, titles and that a separator inside a
        fenced block does not start a new slide.
"""

from pathlib import Path

from rag_lab_generator.ingestion.parsers.reveal_slides import parse_slides, split_slides
from rag_lab_generator.models import Course, DocumentKind


def test_split_slides_ignores_separators_inside_fences(fixtures_dir: Path) -> None:
    body = (fixtures_dir / "slides.md").read_text(encoding="utf-8").split("---\n", 2)[2]
    slides = split_slides(body)
    assert len(slides) == 3
    assert "not a slide separator" in slides[1]


def test_parse_slides_names_slides_after_their_first_heading(fixtures_dir: Path) -> None:
    document = parse_slides(fixtures_dir / "slides.md", "sop2/lecture/shm/slides", Course.SOP2)
    assert document.kind is DocumentKind.LECTURE_SLIDES
    assert [s.title for s in document.sections] == [
        "Shared Memory",
        "What is `mmap()`?",
        "slide 3",
    ]
    assert document.metadata["slides"] == 3
