"""
Role:   Read-only view of the ingested corpus under data/raw for the corpus endpoints.
Input:  settings.raw_dir with <course>/<lab_slug>/{lab.xml, summary.md, manifest.json, src, ...}.
Output: LabDocument models, lab summaries, attachment listings and safe absolute file paths.
Flow:   read_lab_document() delegates to ingestion.lab_xml when that module exists and otherwise
        parses lab.xml with a tolerant lxml reader; list_courses() walks the tree once per call;
        resolve_file() rejects any path escaping the lab folder before the file is served.
"""

import json
import mimetypes
from pathlib import Path
from typing import Any

from lxml import etree

from rag_lab_generator.api.deps import module_attr
from rag_lab_generator.api.schemas import CourseSummary, LabDetailResponse, LabFile, LabSummary
from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    CodeFile,
    Course,
    LabDocument,
    Reference,
    Section,
    Stage,
    Task,
)

LAB_XML = "lab.xml"
SUMMARY_FILES = ("summary.md", "summary.txt")
MANIFEST = "manifest.json"
FILE_GROUPS = ("src", "slides", "extra")
DEFAULT_MEDIA_TYPE = "application/octet-stream"


# ---------------------------------------------------------------- lab.xml


def read_lab_document(path: Path) -> LabDocument:
    """Use the ingestion reader when it exists, else the tolerant reader below."""
    reader = module_attr("rag_lab_generator.ingestion.lab_xml", "read_lab_xml")
    if reader is not None:
        document: LabDocument = reader(path)
        return document
    return parse_lab_xml(path)


def parse_lab_xml(path: Path) -> LabDocument:
    """Map <lab> attributes, <tutorial>/<section>, <tasks>/<task> and the lists onto LabDocument."""
    root = etree.parse(str(path)).getroot()
    slug = root.get("slug") or path.parent.name
    course = _course(root.get("course") or path.parent.parent.name)
    return LabDocument(
        id=root.get("id") or f"{course.value}/{slug}",
        course=course,
        title=_child_text(root, "title") or root.get("title") or slug,
        lang=root.get("lang") or "en",
        source_url=root.get("source_url"),
        local_path=str(path),
        lab_id=root.get("id") or f"{course.value}/{slug}",
        number=root.get("number") or "",
        slug=slug,
        topics=_items(root, "topics"),
        sections=_sections(root),
        tasks=_tasks(root),
        code_files=_code_files(root),
        references=_references(root),
        metadata={"source": "api.corpus"},
    )


def _sections(root: etree._Element) -> list[Section]:
    out: list[Section] = []
    for order, element in enumerate(root.iterfind(".//tutorial/section")):
        out.append(
            Section(
                id=element.get("id") or f"section-{order}",
                title=_child_text(element, "title") or element.get("title") or "",
                level=_int(element.get("level"), 2),
                order=_int(element.get("order"), order),
                text=_body(element, "text"),
                code_refs=_refs(element, "code"),
                parent_id=element.get("parent") or element.get("parent_id") or None,
            )
        )
    return out


def _tasks(root: etree._Element) -> list[Task]:
    out: list[Task] = []
    for order, element in enumerate(root.iterfind(".//tasks/task")):
        out.append(
            Task(
                id=element.get("id") or f"task-{order}",
                title=_child_text(element, "title") or element.get("title") or "",
                statement=_body(element, "statement"),
                stages=_stages(element),
                solution_refs=_refs(element, "solution"),
                attachments=_refs(element, "attachments/file"),
                notes=_child_text(element, "notes"),
                source_url=element.get("source_url"),
            )
        )
    return out


def _stages(task: etree._Element) -> list[Stage]:
    return [
        Stage(n=_int(stage.get("n"), order + 1), text=_all_text(stage))
        for order, stage in enumerate(task.iterfind(".//stages/stage"))
    ]


def _code_files(root: etree._Element) -> list[CodeFile]:
    out: list[CodeFile] = []
    for element in root.iterfind(".//sources/file"):
        ref = element.get("ref") or element.get("path")
        if not ref:
            continue
        out.append(
            CodeFile(
                ref=ref,
                lang=element.get("lang") or "c",
                content=_all_text(element),
                source_url=element.get("source_url"),
            )
        )
    return out


def _references(root: etree._Element) -> list[Reference]:
    out: list[Reference] = []
    for element in root.iterfind(".//references/*"):
        url = element.get("url") or _all_text(element)
        if url:
            out.append(Reference(url=url, title=element.get("title") or ""))
    return out


def _child_text(element: etree._Element, tag: str) -> str:
    child = element.find(tag)
    return _all_text(child) if child is not None else ""


def _body(element: etree._Element, tag: str) -> str:
    """Body text of a section or task: the named child when present, else the element itself."""
    child = element.find(tag)
    if child is not None:
        return _all_text(child)
    return (element.text or "").strip()


def _all_text(element: etree._Element) -> str:
    return "".join(str(part) for part in element.itertext()).strip()


def _refs(element: etree._Element, path: str) -> list[str]:
    """Collect the ref attribute of every child matching the path, ignoring the ones without."""
    return [child.get("ref", "") for child in element.iterfind(path) if child.get("ref")]


def _items(element: etree._Element, container: str) -> list[str]:
    """List values given either as children of <container> or as a comma separated attribute."""
    holder = element.find(container)
    if holder is not None:
        children = [_all_text(child) for child in holder]
        if children:
            return [value for value in children if value]
        text = _all_text(holder)
        return [part.strip() for part in text.split(",") if part.strip()]
    attribute = element.get(container)
    if attribute:
        return [part.strip() for part in attribute.split(",") if part.strip()]
    return []


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _course(name: str | None) -> Course:
    try:
        return Course(str(name).lower())
    except ValueError:
        return Course.EXTERNAL


# ---------------------------------------------------------------- filesystem walk


def lab_dir(settings: Settings, course: str, slug: str) -> Path | None:
    """Locate one lab folder, refusing course or slug values that contain a path separator."""
    if not _safe_name(course) or not _safe_name(slug):
        return None
    candidate = settings.raw_dir / course / slug
    return candidate if (candidate / LAB_XML).is_file() else None


def list_courses(settings: Settings) -> list[CourseSummary]:
    root = settings.raw_dir
    if not root.is_dir():
        return []
    courses: list[CourseSummary] = []
    for course_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        labs = [
            summary
            for lab_path in sorted(p for p in course_dir.iterdir() if p.is_dir())
            if (summary := _lab_summary(course_dir.name, lab_path)) is not None
        ]
        if labs:
            courses.append(
                CourseSummary(course=course_dir.name, n_labs=len(labs), labs=_sorted(labs))
            )
    return courses


def _lab_summary(course: str, path: Path) -> LabSummary | None:
    if not (path / LAB_XML).is_file():
        return None
    try:
        document = read_lab_document(path / LAB_XML)
    except Exception:
        return LabSummary(
            id=f"{course}/{path.name}",
            course=course,
            slug=path.name,
            title=path.name,
            number="",
            n_tasks=0,
            n_sections=0,
            n_files=len(list_files(path)),
            has_summary=_summary_path(path) is not None,
        )
    return LabSummary(
        id=document.id,
        course=document.course.value,
        slug=document.slug,
        title=document.title,
        number=document.number,
        n_tasks=len(document.tasks),
        n_sections=len(document.sections),
        n_files=len(list_files(path)),
        has_summary=_summary_path(path) is not None,
    )


def _sorted(labs: list[LabSummary]) -> list[LabSummary]:
    """Order labs by the numeric part of their number, keeping non numeric ones last."""

    def key(lab: LabSummary) -> tuple[float, str]:
        try:
            return (float(lab.number), lab.slug)
        except ValueError:
            return (float("inf"), lab.slug)

    return sorted(labs, key=key)


def load_lab(settings: Settings, course: str, slug: str) -> LabDetailResponse | None:
    path = lab_dir(settings, course, slug)
    if path is None:
        return None
    summary_path = _summary_path(path)
    return LabDetailResponse(
        lab=read_lab_document(path / LAB_XML),
        summary=summary_path.read_text(encoding="utf-8") if summary_path else None,
        manifest=_manifest(path),
        files=list_files(path),
    )


def list_files(path: Path) -> list[LabFile]:
    out: list[LabFile] = []
    for group in FILE_GROUPS:
        group_dir = path / group
        if not group_dir.is_dir():
            continue
        for file_path in sorted(p for p in group_dir.rglob("*") if p.is_file()):
            out.append(
                LabFile(
                    path=file_path.relative_to(path).as_posix(),
                    group=group,
                    size=file_path.stat().st_size,
                    media_type=media_type(file_path),
                )
            )
    return out


def resolve_file(settings: Settings, course: str, slug: str, relative: str) -> Path | None:
    """Return the absolute path of an attachment, or None when it escapes the lab folder."""
    path = lab_dir(settings, course, slug)
    if path is None:
        return None
    target = (path / relative).resolve()
    root = path.resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return (
        "text/plain"
        if path.suffix in {".c", ".h", ".md", ".txt", ".sh", ""}
        else DEFAULT_MEDIA_TYPE
    )


def _summary_path(path: Path) -> Path | None:
    for name in SUMMARY_FILES:
        candidate = path / name
        if candidate.is_file():
            return candidate
    return None


def _manifest(path: Path) -> dict[str, Any] | None:
    candidate = path / MANIFEST
    if not candidate.is_file():
        return None
    try:
        loaded: Any = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _safe_name(value: str) -> bool:
    return bool(value) and "/" not in value and "\\" not in value and value not in {".", ".."}
