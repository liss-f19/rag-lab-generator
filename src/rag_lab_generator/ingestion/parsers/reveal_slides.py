"""
Role:   Parser for the reveal.js decks of the SOP2 lectures (type: presentation pages).
Input:  A slides markdown file (or its text) plus the document id, course and source URL.
Output: Document of kind LECTURE_SLIDES with one Section per slide.
Flow:   Strips the front matter, splits the body on horizontal-rule slide separators while
        keeping fenced code blocks intact, and names each slide after its first heading.
"""

import re
from pathlib import Path

from rag_lab_generator.ingestion.parsers.hugo_markdown import read_page, slugify
from rag_lab_generator.ingestion.parsers.shortcodes import mask_fences
from rag_lab_generator.models import Course, Document, DocumentKind, Section

SEPARATOR_RE = re.compile(r"^[ \t]*(?:---+|___+|\*\*\*+)[ \t]*$", re.M)
HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$", re.M)


def split_slides(body: str) -> list[str]:
    """Split a reveal deck body into slide bodies, ignoring separators inside code fences."""
    masked = mask_fences(body)
    cuts = [0]
    for match in SEPARATOR_RE.finditer(masked):
        cuts.append(match.start())
    cuts.append(len(body))

    slides: list[str] = []
    for index in range(len(cuts) - 1):
        raw = body[cuts[index] : cuts[index + 1]]
        raw = SEPARATOR_RE.sub("", raw, count=1) if index else raw
        if raw.strip():
            slides.append(raw.strip("\n"))
    return slides


def parse_slides(
    path: Path,
    document_id: str,
    course: Course,
    source_url: str | None = None,
    title: str | None = None,
) -> Document:
    """Turn one reveal deck into a Document with one Section per slide."""
    metadata, body = read_page(path)
    sections: list[Section] = []
    used: dict[str, int] = {}
    for order, slide in enumerate(split_slides(body)):
        heading = HEADING_RE.search(slide)
        slide_title = heading.group(1).strip() if heading else f"slide {order + 1}"
        base = slugify(slide_title)
        used[base] = used.get(base, 0) + 1
        sections.append(
            Section(
                id=base if used[base] == 1 else f"{base}-{used[base]}",
                title=slide_title,
                level=2,
                order=order,
                text=slide,
            )
        )
    return Document(
        id=document_id,
        course=course,
        kind=DocumentKind.LECTURE_SLIDES,
        title=title or str(metadata.get("title") or path.parent.name),
        source_url=source_url,
        local_path=str(path),
        sections=sections,
        metadata={"slides": len(sections)},
    )
