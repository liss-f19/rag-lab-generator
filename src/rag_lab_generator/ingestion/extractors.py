"""Text extraction for the supported source formats (FR-02, FR-03).

Every extractor returns text blocks that keep the position of the text in the
source: the heading path for Markdown and HTML, the page number for PDF.
"""

from __future__ import annotations

import io
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from rag_lab_generator.domain.errors import (
    ExtractionError,
    UnsupportedDocumentFormatError,
)
from rag_lab_generator.domain.models import TextBlock
from rag_lab_generator.domain.ports import TextExtractor

MARKDOWN = "text/markdown"
PLAIN_TEXT = "text/plain"
HTML = "text/html"
PDF = "application/pdf"

_MEDIA_TYPES_BY_SUFFIX = {
    ".md": MARKDOWN,
    ".markdown": MARKDOWN,
    ".txt": PLAIN_TEXT,
    ".html": HTML,
    ".htm": HTML,
    ".pdf": PDF,
}
ACCEPTED_FORMATS = ["pdf", "html", "txt", "md"]


def media_type_for(filename: str) -> str:
    """Return the media type for a file name, or raise for unsupported formats."""
    suffix = PurePath(filename).suffix.lower()
    try:
        return _MEDIA_TYPES_BY_SUFFIX[suffix]
    except KeyError:
        raise UnsupportedDocumentFormatError(
            "The uploaded file type is not supported.",
            details={"accepted_formats": ACCEPTED_FORMATS, "filename": filename},
        ) from None


def check_signature(media_type: str, data: bytes) -> None:
    """Reject files whose content obviously does not match their extension."""
    if media_type == PDF and not data.startswith(b"%PDF-"):
        raise UnsupportedDocumentFormatError(
            "The file has a .pdf extension but is not a PDF document.",
            details={"accepted_formats": ACCEPTED_FORMATS},
        )


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            "The file is not valid UTF-8 text. Save it with UTF-8 encoding and upload it again.",
            details={"byte_offset": exc.start},
        ) from exc


class PlainTextExtractor:
    def extract(self, data: bytes) -> list[TextBlock]:
        text = normalize_text(decode_text(data))
        return [TextBlock(text=text)] if text.strip() else []


class _SectionCollector:
    """Accumulates lines of the current section and tracks the heading path."""

    def __init__(self) -> None:
        self.blocks: list[TextBlock] = []
        self._path: list[tuple[int, str]] = []
        self._lines: list[str] = []

    def add_line(self, line: str) -> None:
        self._lines.append(line)

    def open_heading(self, level: int, title: str) -> None:
        self.flush()
        while self._path and self._path[-1][0] >= level:
            self._path.pop()
        if title:
            self._path.append((level, title))

    def flush(self) -> None:
        text = normalize_text("\n".join(self._lines))
        self._lines = []
        if text.strip():
            path = tuple(title for _, title in self._path)
            self.blocks.append(TextBlock(text=text, section_path=path))


_MD_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_MD_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def _clean_heading(title: str) -> str:
    return re.sub(r"[*_`]", "", title).strip()


class MarkdownExtractor:
    """Splits Markdown by ATX headings; fenced code blocks are kept intact."""

    def extract(self, data: bytes) -> list[TextBlock]:
        collector = _SectionCollector()
        fence: str | None = None
        for line in decode_text(data).replace("\r\n", "\n").split("\n"):
            fence_match = _MD_FENCE.match(line)
            if fence_match:
                marker = fence_match.group(1)
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                collector.add_line(line)
                continue
            heading = None if fence is not None else _MD_HEADING.match(line)
            if heading:
                collector.open_heading(
                    len(heading.group(1)), _clean_heading(heading.group(2))
                )
            else:
                collector.add_line(line)
        collector.flush()
        return collector.blocks


_HTML_SKIPPED = {"script", "style", "noscript", "template", "head", "svg"}
_HTML_BLOCKS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "footer",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}
_HTML_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.collector = _SectionCollector()
        self._skip_depth = 0
        self._pre_depth = 0
        self._heading_level: int | None = None
        self._heading_parts: list[str] = []
        self._parts: list[str] = []
        self._at_line_start = True

    def _newline(self, separator: str) -> None:
        self._parts.append(separator)
        self._at_line_start = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _HTML_SKIPPED:
            self._skip_depth += 1
        elif tag in _HTML_HEADINGS:
            self._heading_level = _HTML_HEADINGS[tag]
            self._heading_parts = []
        elif tag == "br":
            self._newline("\n")
        elif tag in _HTML_BLOCKS:
            self._newline("\n\n")
            if tag == "pre":
                self._pre_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _HTML_SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _HTML_HEADINGS and self._heading_level is not None:
            self._end_section()
            title = re.sub(r"\s+", " ", "".join(self._heading_parts)).strip()
            self.collector.open_heading(self._heading_level, title)
            self._heading_level = None
        elif tag in _HTML_BLOCKS:
            self._newline("\n\n")
            if tag == "pre":
                self._pre_depth = max(0, self._pre_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._heading_level is not None:
            self._heading_parts.append(data)
        elif self._pre_depth:
            self._parts.append(data)
            self._at_line_start = data.endswith("\n")
        else:
            text = re.sub(r"\s+", " ", data)
            if self._at_line_start:
                text = text.lstrip()
            if text:
                self._parts.append(text)
                self._at_line_start = False

    def _end_section(self) -> None:
        for line in "".join(self._parts).split("\n"):
            self.collector.add_line(line)
        self._parts = []
        self._at_line_start = True

    def close(self) -> None:
        super().close()
        self._end_section()
        self.collector.flush()


class HtmlExtractor:
    """Extracts visible text; h1-h6 headings define the section path."""

    def extract(self, data: bytes) -> list[TextBlock]:
        parser = _HtmlTextParser()
        parser.feed(decode_text(data))
        parser.close()
        return parser.collector.blocks


class PdfExtractor:
    """One block per page, so that evidence can cite the page number."""

    def extract(self, data: bytes) -> list[TextBlock]:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ExtractionError("The PDF file is password-protected.")
            blocks = []
            for number, page in enumerate(reader.pages, start=1):
                text = normalize_text(page.extract_text() or "")
                if text.strip():
                    blocks.append(TextBlock(text=text, page_number=number))
            return blocks
        except (PdfReadError, ValueError, KeyError) as exc:
            raise ExtractionError(
                "The PDF file is damaged or cannot be parsed."
            ) from exc


_EXTRACTORS: dict[str, TextExtractor] = {
    MARKDOWN: MarkdownExtractor(),
    PLAIN_TEXT: PlainTextExtractor(),
    HTML: HtmlExtractor(),
    PDF: PdfExtractor(),
}


def extractor_for(media_type: str) -> TextExtractor:
    try:
        return _EXTRACTORS[media_type]
    except KeyError:
        raise UnsupportedDocumentFormatError(
            f"No text extractor for media type {media_type}.",
            details={"accepted_formats": ACCEPTED_FORMATS},
        ) from None
