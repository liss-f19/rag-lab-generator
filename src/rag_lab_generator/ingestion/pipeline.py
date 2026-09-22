"""
Role:   Ingestion entry points: build data/raw from the sources and read it back into models.
Input:  Settings, the list of courses to process and the force flag; data/raw for reading back.
Output: IngestReport with per-course counts; list[Document] for the retrieval layer.
Flow:   run_ingest fetches both sources, parses every lab, lecture and course page, lays the
        tree out through layout.py and writes the summaries; load_documents walks data/raw and
        rebuilds LabDocument, lecture, course info, summary and external documents without
        touching the network.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion import layout
from rag_lab_generator.ingestion.lab_xml import read_lab_xml
from rag_lab_generator.ingestion.parsers.hugo_markdown import (
    LAB_SLUGS,
    parse_info_page,
    parse_lab,
    split_sections,
)
from rag_lab_generator.ingestion.parsers.pdf import document_from_text
from rag_lab_generator.ingestion.parsers.reveal_slides import parse_slides
from rag_lab_generator.ingestion.parsers.shortcodes import lang_of
from rag_lab_generator.ingestion.summarizer import render_pdf, summarize_lab
from rag_lab_generator.models import (
    Course,
    Document,
    DocumentKind,
    LabDocument,
    Section,
)
from rag_lab_generator.registry import create

COURSE_DIR = "_course"
LECTURES_DIR = "_lectures"
COURSE_EXTRA_DIR = layout.COURSE_EXTRA_DIR
REPO_BLOB_URL = "https://github.com/SOP-MINI/sop-site/blob/master"
TEXT_SUFFIXES: frozenset[str] = frozenset({".c", ".h", ".cpp", ".cc", ".py", ".sh", ".txt", ".md"})


class CourseCounts(BaseModel):
    """What one course contributed to data/raw."""

    labs: int = 0
    sections: int = 0
    tasks: int = 0
    code_files: int = 0
    lectures: int = 0
    lecture_pdfs: int = 0
    course_pages: int = 0
    external_files: int = 0


class IngestReport(BaseModel):
    """Result of one run_ingest call."""

    raw_dir: str
    courses: dict[str, CourseCounts] = Field(default_factory=dict)
    summaries: int = 0
    skipped: list[str] = Field(default_factory=list)

    @property
    def total_labs(self) -> int:
        return sum(counts.labs for counts in self.courses.values())


def lab_dirs(content_root: Path, course: Course) -> list[tuple[str, Path]]:
    """List (hugo dir name, index page) of every lab of one course, in site order."""
    root = content_root / course.value / "lab"
    found: list[tuple[str, Path]] = []
    if not root.is_dir():
        return found
    for path in sorted(root.iterdir()):
        if path.is_dir():
            for name in ("_index.en.md", "index.en.md"):
                if (path / name).is_file():
                    found.append((path.name, path / name))
                    break
        elif path.name.endswith(".en.md") and path.name != "_index.en.md":
            found.append((path.name.removesuffix(".en.md"), path))
    return [item for item in found if f"{course.value}/{item[0]}" in LAB_SLUGS]


# ---------------------------------------------------------------- ingest


def run_ingest(settings: Settings, courses: list[str], force: bool = False) -> IngestReport:
    """Fetch every source and build the complete data/raw tree for the given courses."""
    return _run_ingest(settings, courses, force, summaries=True)


def run_ingest_without_summaries(
    settings: Settings, courses: list[str], force: bool = False
) -> IngestReport:
    """Same as run_ingest but leaves summary.md and summary.pdf untouched."""
    return _run_ingest(settings, courses, force, summaries=False)


def _run_ingest(
    settings: Settings, courses: list[str], force: bool, summaries: bool
) -> IngestReport:
    external = settings.external_dir
    clone = external / "sop-site"
    create("source", "sop_site", settings=settings).fetch(clone, force=force)
    create("source", "kozlowski", settings=settings).fetch(external / "kozlowski", force=force)
    layout.extract_external_sidecars(external, force=force)

    content_root = clone / "content"
    static_files = clone / "static" / "files"
    mapping = layout.load_mapping()
    course_mapping = layout.load_course_mapping()
    file_index = layout.build_file_index(content_root, static_files)
    report = IngestReport(raw_dir=str(settings.raw_dir))
    llm = create("llm", settings.llm_provider, settings=settings) if summaries else None
    wanted = [Course(name) for name in courses]
    labs = {course: lab_dirs(content_root, course) for course in wanted}

    # Lectures of another course are copied too when a requested lab maps to them.
    needed: dict[Course, set[str]] = {course: set() for course in wanted}
    for course in wanted:
        for hugo_dir, _ in labs[course]:
            for topic in mapping.get(f"{course.value}/{hugo_dir}", layout.LabMapping()).lectures:
                topic_course, _, topic_name = topic.partition("/")
                needed.setdefault(Course(topic_course), set()).add(topic_name)

    for course, topics in needed.items():
        counts = report.courses.setdefault(course.value, CourseCounts())
        for topic, directory in layout.lecture_dirs(content_root, course):
            if course not in wanted and topic not in topics:
                continue
            written = layout.copy_lecture_tree(
                directory, settings.raw_dir / course.value / LECTURES_DIR / topic
            )
            counts.lectures += 1
            counts.lecture_pdfs += sum(1 for name in written if name.endswith(".pdf"))

    for course in wanted:
        counts = report.courses.setdefault(course.value, CourseCounts())
        course_dir = settings.raw_dir / course.value

        for page_name, path in layout.course_info_pages(content_root, clone, course):
            inside = content_root in path.parents
            document = parse_info_page(
                path,
                content_root if inside else None,
                course,
                page_name,
                source_url=None if inside else f"{REPO_BLOB_URL}/{path.name}",
            )
            target = course_dir / COURSE_DIR / f"{page_name}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_document_markdown(document), encoding="utf-8")
            counts.course_pages += 1

        extra = layout.build_course_extra(
            course_dir, external, course_mapping.get(course.value, layout.CourseMapping())
        )
        counts.external_files += len(extra)

        for hugo_dir, index_path in labs[course]:
            lab = parse_lab(index_path, content_root, course, hugo_dir, static_files)
            manifest = layout.build_lab(
                lab,
                settings.raw_dir,
                file_index,
                external,
                mapping.get(lab.id, layout.LabMapping()),
            )
            counts.labs += 1
            counts.sections += len(lab.sections)
            counts.tasks += len(lab.tasks)
            counts.code_files += len(manifest.src)
            counts.external_files += len(manifest.extra)
            report.skipped.extend(
                f"{lab.id}:{file.ref}"
                for file in lab.code_files
                if layout.src_name(file.ref) not in manifest.src
            )
            if llm is not None:
                render_pdf(summarize_lab(lab, llm, settings.raw_dir / course.value / lab.slug))
                report.summaries += 1

    return report


def regenerate_summaries(
    settings: Settings, courses: list[str], lab: str | None = None
) -> list[str]:
    """Rewrite summary.md and summary.pdf of the already ingested labs with the current llm."""
    llm = create("llm", settings.llm_provider, settings=settings)
    written: list[str] = []
    for document in load_documents(settings, courses):
        if not isinstance(document, LabDocument):
            continue
        if lab is not None and lab not in {document.id, document.slug}:
            continue
        lab_dir = settings.raw_dir / document.course.value / document.slug
        render_pdf(summarize_lab(document, llm, lab_dir))
        written.append(document.id)
    return written


def _document_markdown(document: Document) -> str:
    """Render a parsed page back to markdown with a small provenance header."""
    header = [f"# {document.title}", ""]
    if document.source_url:
        header += [f"Source: {document.source_url}", ""]
    return "\n".join(header) + "\n\n".join(section.text for section in document.sections) + "\n"


# ---------------------------------------------------------------- load back


def load_documents(settings: Settings, courses: list[str] | None = None) -> list[Document]:
    """Read data/raw back into Document models without fetching anything."""
    wanted = [Course(name) for name in (courses or [c.value for c in (Course.SOP1, Course.SOP2)])]
    mapping = layout.load_mapping()
    external_owners = _external_owners(mapping)
    documents: list[Document] = []
    for course in wanted:
        course_dir = settings.raw_dir / course.value
        if not course_dir.is_dir():
            continue
        documents.extend(_load_course_info(course_dir, course))
        documents.extend(_load_external(course_dir / COURSE_EXTRA_DIR, course, None, {}))
        documents.extend(_load_lectures(course_dir, course))
        for lab_dir in sorted(p for p in course_dir.iterdir() if (p / "lab.xml").is_file()):
            documents.extend(_load_lab(lab_dir, course, external_owners))

    # Kozlowski material is background reading for students new to Unix, the site is the course.
    for document in documents:
        document.metadata["support"] = (
            "background" if document.kind is DocumentKind.EXTERNAL_PDF else "primary"
        )
    return documents


def _external_owners(mapping: dict[str, layout.LabMapping]) -> dict[str, list[str]]:
    """Invert mapping.yaml: external file name -> ids of the labs that use it."""
    owners: dict[str, list[str]] = {}
    for lab_id, entry in sorted(mapping.items()):
        for relative in entry.kozlowski:
            owners.setdefault(Path(relative).name, []).append(lab_id)
    return owners


def _load_course_info(course_dir: Path, course: Course) -> list[Document]:
    documents: list[Document] = []
    for path in sorted((course_dir / COURSE_DIR).glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        sections = split_sections(text)
        documents.append(
            Document(
                id=f"{course.value}/course/{path.stem}",
                course=course,
                kind=DocumentKind.COURSE_INFO,
                title=_first_heading(text, path.stem),
                local_path=str(path),
                sections=sections,
                metadata={"page": path.stem},
            )
        )
    return documents


def _load_lectures(course_dir: Path, course: Course) -> list[Document]:
    documents: list[Document] = []
    root = course_dir / LECTURES_DIR
    if not root.is_dir():
        return documents
    for topic_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        topic = topic_dir.name
        index = topic_dir / "index.md"
        if index.is_file():
            text = index.read_text(encoding="utf-8", errors="replace")
            documents.append(
                Document(
                    id=f"{course.value}/lecture/{topic}/index",
                    course=course,
                    kind=DocumentKind.LECTURE_INDEX,
                    title=_first_heading(text, topic),
                    local_path=str(index),
                    sections=split_sections(text),
                    metadata={"topic": topic},
                )
            )
        slides = topic_dir / "slides.md"
        if slides.is_file():
            document = parse_slides(
                slides, f"{course.value}/lecture/{topic}/slides", course, title=f"{topic} slides"
            )
            document.metadata["topic"] = topic
            documents.append(document)
        for sidecar in sorted(topic_dir.glob("*.txt")):
            documents.append(
                document_from_text(
                    sidecar.read_text(encoding="utf-8", errors="replace"),
                    f"{course.value}/lecture/{topic}/{sidecar.stem}",
                    course,
                    DocumentKind.LECTURE_PDF,
                    sidecar.stem,
                    local_path=sidecar.with_suffix(".pdf"),
                )
            )
        for code in sorted((topic_dir / "code").rglob("*")):
            if not code.is_file():
                continue
            relative = code.relative_to(topic_dir / "code").as_posix()
            documents.append(
                _code_document(
                    code,
                    f"{course.value}/lecture/{topic}/code/{relative}",
                    course,
                    DocumentKind.LECTURE_CODE,
                    metadata={"topic": topic},
                )
            )
    return documents


def _load_lab(lab_dir: Path, course: Course, owners: dict[str, list[str]]) -> list[Document]:
    lab = read_lab_xml(lab_dir / "lab.xml")
    lab.local_path = str(lab_dir)
    lab.metadata = {
        "slug": lab.slug,
        "number": lab.number,
        "n_tasks": len(lab.tasks),
        "n_code_files": len(lab.code_files),
        "topics": lab.topics,
    }
    documents: list[Document] = [lab]

    summary = lab_dir / "summary.md"
    if summary.is_file():
        text = summary.read_text(encoding="utf-8", errors="replace")
        documents.append(
            Document(
                id=f"{lab.id}/summary",
                course=course,
                kind=DocumentKind.SUMMARY,
                title=f"Summary of {lab.title}",
                lab_id=lab.id,
                local_path=str(summary),
                sections=split_sections(text),
                metadata={"slug": lab.slug},
            )
        )

    documents.extend(_load_external(lab_dir / "extra", course, lab.id, owners))
    return documents


def _load_external(
    directory: Path, course: Course, lab_id: str | None, owners: dict[str, list[str]]
) -> list[Document]:
    """Build the external documents of one extra/ or _extra/ directory."""
    documents: list[Document] = []
    for path in sorted(directory.glob("*")):
        # A pdf is represented by its .txt sidecar, which carries the page markers.
        if not path.is_file() or path.suffix.lower() == ".pdf":
            continue
        source = path.with_suffix(".pdf") if path.with_suffix(".pdf").is_file() else path
        stem = path.stem
        base_id = f"external/kozlowski/{_external_group(stem)}/{stem}"
        multiple = len(owners.get(source.name, [])) > 1
        document_id = f"{base_id}@{lab_id}" if multiple and lab_id else base_id
        if path.suffix.lower() == ".sh":
            document = _code_document(
                path, document_id, course, DocumentKind.EXTERNAL_PDF, metadata={"format": "sh"}
            )
            document.lab_id = lab_id
            documents.append(document)
            continue
        documents.append(
            document_from_text(
                path.read_text(encoding="utf-8", errors="replace"),
                document_id,
                course,
                DocumentKind.EXTERNAL_PDF,
                stem,
                lab_id=lab_id,
                local_path=source,
            )
        )
    return documents


def _external_group(stem: str) -> str:
    """Tell whether an external file came from the unix or the tcpip directory."""
    return "tcpip" if stem.startswith(("lecture_", "lab_")) else "unix"


def _code_document(
    path: Path,
    document_id: str,
    course: Course,
    kind: DocumentKind,
    metadata: dict[str, str] | None = None,
) -> Document:
    """Wrap one code file into a Document holding a single fenced section."""
    body = path.read_text(encoding="utf-8", errors="replace")
    language = lang_of(path.name)
    return Document(
        id=document_id,
        course=course,
        kind=kind,
        title=path.name,
        local_path=str(path),
        sections=[
            Section(
                id=path.name.replace(".", "-"),
                title=path.name,
                level=2,
                order=0,
                text=f"```{language}\n{body.rstrip()}\n```",
            )
        ],
        metadata={"lang": language, **(metadata or {})},
    )


def _first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return fallback
