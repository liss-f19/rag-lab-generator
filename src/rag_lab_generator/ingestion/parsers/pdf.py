"""
Role:   PDF text extraction for lecture slides and external course material.
Input:  A pdf path plus the document id, course, kind and optional owning lab id.
Output: Document with one Section per non-empty page; a <name>.txt sidecar next to the pdf.
Flow:   Opens the file with PyMuPDF, extracts the text of every page, drops empty pages,
        writes the concatenated text to the sidecar and returns the Document model.
"""

import re
from pathlib import Path

from rag_lab_generator.models import Course, Document, DocumentKind, Section

PAGE_SEPARATOR = "\n\n--- page %d ---\n\n"
PAGE_MARKER_RE = re.compile(r"^--- page (\d+) ---$", re.M)


def extract_pages(path: Path) -> list[str]:
    """Return the text of every page of a pdf, empty pages included as empty strings."""
    import pymupdf  # optional `ingest` extra, loaded only when a pdf is parsed

    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        return [page.get_text().strip() for page in document]


def write_sidecar(path: Path, pages: list[str] | None = None) -> Path:
    """Write <name>.txt next to the pdf and return the sidecar path."""
    pages = extract_pages(path) if pages is None else pages
    sidecar = path.with_suffix(".txt")
    body = "".join(
        (PAGE_SEPARATOR % (number + 1)) + text for number, text in enumerate(pages) if text
    )
    sidecar.write_text(body.lstrip("\n"), encoding="utf-8")
    return sidecar


def parse_pdf(
    path: Path,
    document_id: str,
    course: Course,
    kind: DocumentKind = DocumentKind.LECTURE_PDF,
    source_url: str | None = None,
    lab_id: str | None = None,
    title: str | None = None,
    sidecar: bool = True,
) -> Document:
    """Extract a pdf into a Document with one Section per non-empty page."""
    pages = extract_pages(path)
    if sidecar:
        write_sidecar(path, pages)
    sections = [
        Section(
            id=f"page-{number + 1}", title=f"page {number + 1}", level=2, order=number, text=text
        )
        for number, text in enumerate(pages)
        if text
    ]
    return Document(
        id=document_id,
        course=course,
        kind=kind,
        title=title or path.stem,
        source_url=source_url,
        local_path=str(path),
        lab_id=lab_id,
        sections=sections,
        metadata={"pages": len(pages), "pages_with_text": len(sections), "format": "pdf"},
    )


def document_from_text(
    text: str,
    document_id: str,
    course: Course,
    kind: DocumentKind,
    title: str,
    source_url: str | None = None,
    lab_id: str | None = None,
    local_path: Path | None = None,
) -> Document:
    """Build a Document from a .txt sidecar, restoring one Section per page marker."""
    parts = PAGE_MARKER_RE.split(text)
    pairs: list[tuple[int, str]] = []
    if parts[0].strip():
        pairs.append((1, parts[0].strip()))
    for index in range(1, len(parts) - 1, 2):
        body = parts[index + 1].strip()
        if body:
            pairs.append((int(parts[index]), body))
    sections = [
        Section(id=f"page-{number}", title=f"page {number}", level=2, order=order, text=body)
        for order, (number, body) in enumerate(pairs)
    ]
    return Document(
        id=document_id,
        course=course,
        kind=kind,
        title=title,
        source_url=source_url,
        local_path=str(local_path) if local_path is not None else None,
        lab_id=lab_id,
        sections=sections,
        metadata={"format": "pdf", "pages_with_text": len(sections)},
    )
