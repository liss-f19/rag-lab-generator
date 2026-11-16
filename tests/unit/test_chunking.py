from itertools import pairwise

import pytest

from rag_lab_generator.domain.models import TextBlock
from rag_lab_generator.ingestion.chunking import StructuredChunker


def test_paragraphs_are_packed_up_to_the_limit() -> None:
    paragraphs = [f"Paragraph {number} " + "x" * 40 for number in range(10)]
    pieces = StructuredChunker(max_chars=120, overlap_chars=0).split(
        [TextBlock("\n\n".join(paragraphs), ("Section",))]
    )
    assert all(len(piece.content) <= 120 for piece in pieces)
    assert "\n\n".join(piece.content for piece in pieces) == "\n\n".join(paragraphs)
    assert {piece.section_path for piece in pieces} == {("Section",)}


def test_fragments_do_not_cross_sections_or_pages() -> None:
    pieces = StructuredChunker(max_chars=500).split(
        [
            TextBlock("short a", ("A",)),
            TextBlock("short b", ("B",)),
            TextBlock("page one", (), 1),
            TextBlock("page two", (), 2),
        ]
    )
    assert [
        (piece.content, piece.section_path, piece.page_number) for piece in pieces
    ] == [
        ("short a", ("A",), None),
        ("short b", ("B",), None),
        ("page one", (), 1),
        ("page two", (), 2),
    ]


def test_code_fence_with_blank_lines_stays_together() -> None:
    code = "```c\nint main(void)\n{\n\n    return 0;\n}\n```"
    chunker = StructuredChunker(max_chars=200, overlap_chars=20)
    pieces = chunker.split([TextBlock(f"Intro.\n\n{code}\n\nOutro.")])
    assert len(pieces) == 1
    assert code in pieces[0].content


def test_long_paragraph_is_split_into_overlapping_windows() -> None:
    words = [f"word{number:03d}" for number in range(120)]
    text = " ".join(words)
    pieces = StructuredChunker(max_chars=200, overlap_chars=40).split([TextBlock(text)])
    assert len(pieces) > 1
    assert all(len(piece.content) <= 200 for piece in pieces)
    for previous, following in pairwise(pieces):
        assert following.content.split()[0] in previous.content
    covered = set()
    for piece in pieces:
        covered.update(piece.content.split())
    assert covered == set(words)


def test_text_without_spaces_is_still_split() -> None:
    pieces = StructuredChunker(max_chars=100, overlap_chars=10).split(
        [TextBlock("y" * 450)]
    )
    assert sum(len(piece.content) for piece in pieces) >= 450
    assert all(len(piece.content) <= 100 for piece in pieces)


@pytest.mark.parametrize(("max_chars", "overlap"), [(50, 0), (200, 100), (200, -1)])
def test_invalid_configuration_is_rejected(max_chars: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        StructuredChunker(max_chars=max_chars, overlap_chars=overlap)
