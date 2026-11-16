"""
Role:   Unit tests of the lab summarizer and its pdf rendering.
Input:  The fixture lab.xml and the fake llm from the registry.
Output: Assertions that summary.md keeps the deterministic outline and that summary.pdf is real.
Flow:   Reads the fixture lab, summarizes it with the fake provider into a tmp directory and
        renders the markdown to pdf.
"""

from pathlib import Path

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.lab_xml import read_lab_xml
from rag_lab_generator.ingestion.summarizer import build_outline, render_pdf, summarize_lab
from rag_lab_generator.registry import create


def test_outline_lists_sections_tasks_and_topics(fixtures_dir: Path) -> None:
    lab = read_lab_xml(fixtures_dir / "corpus/raw/sop1/l1_filesystem/lab.xml")
    outline = build_outline(lab)
    assert "## Topics" in outline
    assert "`opendir`" in outline
    assert "Reading a directory" in outline
    assert "example1: Example task 1" in outline


def test_fake_llm_summary_still_contains_the_outline(fixtures_dir: Path, tmp_path: Path) -> None:
    lab = read_lab_xml(fixtures_dir / "corpus/raw/sop1/l1_filesystem/lab.xml")
    llm = create("llm", "fake", settings=Settings(data_dir=tmp_path))
    target = summarize_lab(lab, llm, tmp_path)
    text = target.read_text(encoding="utf-8")
    assert target.name == "summary.md"
    assert "[fake-llm]" in text
    assert "## Tutorial outline" in text


def test_render_pdf_writes_a_real_pdf(fixtures_dir: Path, tmp_path: Path) -> None:
    markdown = tmp_path / "summary.md"
    markdown.write_text("# Title\n\nSome text with `code`.\n", encoding="utf-8")
    pdf = render_pdf(markdown)
    assert pdf.read_bytes().startswith(b"%PDF")
