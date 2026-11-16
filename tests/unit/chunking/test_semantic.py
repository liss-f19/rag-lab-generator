"""
Role:   Unit tests for the semantic chunker driven by the deterministic fake embedder.
Input:  `settings` fixture (embedding_provider="fake") and hand-written paragraph texts.
Output: Assertions; no side effects.
Flow:   Checks that identical paragraphs are merged, that dissimilar ones are separated with the
        repeated-paragraph overlap, that chunk_size is respected, that fenced code and tiny
        pieces are never left alone and that a missing embedder degrades to size-only grouping.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.chunking.semantic import SemanticChunker, split_paragraphs
from rag_lab_generator.registry import create


def test_identical_paragraphs_are_grouped(settings: Settings) -> None:
    chunker = SemanticChunker(settings)
    text = "\n\n".join(["Directories are read with readdir."] * 4)
    pieces = chunker.split_text(text)
    assert len(pieces) == 1
    assert len(split_paragraphs(pieces[0])) == 4


def test_dissimilar_paragraphs_are_separated(settings: Settings) -> None:
    chunker = SemanticChunker(settings.model_copy(update={"chunk_size": 100}))
    paragraphs = [
        "Directories are read with opendir and readdir.",
        "Semaphores protect a critical section between processes.",
        "Signals interrupt a running process asynchronously.",
    ]
    pieces = chunker.split_text("\n\n".join(paragraphs))
    assert len(pieces) == len(paragraphs)


def test_overlap_repeats_the_previous_paragraph(settings: Settings) -> None:
    chunker = SemanticChunker(settings.model_copy(update={"chunk_size": 30}))
    paragraphs = ["alpha beta", "gamma delta", "epsilon zeta"]
    pieces = chunker.split_text("\n\n".join(paragraphs), overlap_ratio=1.0)
    assert len(pieces) > 1
    for previous, current in zip(pieces, pieces[1:], strict=False):
        assert split_paragraphs(current)[0] == split_paragraphs(previous)[-1]


def test_pieces_respect_chunk_size(settings: Settings) -> None:
    small = settings.model_copy(update={"chunk_size": 200})
    text = "\n\n".join(f"Paragraph number {i} about system calls. " * 3 for i in range(12))
    pieces = SemanticChunker(small).split_text(text)
    assert pieces
    assert all(len(piece) <= 200 for piece in pieces)


def test_falls_back_to_size_grouping_without_embedder(settings: Settings) -> None:
    broken = settings.model_copy(update={"embedding_provider": "does_not_exist", "chunk_size": 60})
    chunker = SemanticChunker(broken)
    text = "\n\n".join(["abcde fghij klmno"] * 6)
    pieces = chunker.split_text(text)
    assert len(pieces) > 1
    assert all(len(piece) <= 60 for piece in pieces)


def test_registered_semantic_chunker_uses_settings_embedder(settings: Settings) -> None:
    chunker = create("chunker", "semantic", settings=settings)
    assert chunker.name == "semantic"
    assert chunker.similarity_threshold == 0.75


def test_fenced_code_is_one_paragraph() -> None:
    text = "Intro line.\n\n```c\n#include <stdio.h>\n\nint main(void)\n{\n}\n```\n\nOutro."
    paragraphs = split_paragraphs(text)
    assert len(paragraphs) == 3
    assert paragraphs[1].startswith("```c") and paragraphs[1].endswith("```")


def test_tiny_dissimilar_pieces_are_folded_together(settings: Settings) -> None:
    chunker = SemanticChunker(settings)
    text = (
        "### Stage 3\n\n- Add chunking.\n- Add removal\n\nSolution **prog.c**:\n\n```c\nint x;\n```"
    )
    pieces = chunker.split_text(text, overlap_ratio=0.1)
    assert pieces == [text]


def test_folding_drops_the_repeated_overlap_paragraph(settings: Settings) -> None:
    chunker = SemanticChunker(settings)
    pieces = chunker.split_text("one alpha\n\ntwo beta\n\nthree gamma", overlap_ratio=1.0)
    assert pieces == ["one alpha\n\ntwo beta\n\nthree gamma"]
