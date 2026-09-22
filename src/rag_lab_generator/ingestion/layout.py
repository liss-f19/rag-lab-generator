"""
Role:   Builder of the data/raw tree: one directory per lab, plus _lectures and _course.
Input:  Parsed models, the sop-site clone, the kozlowski downloads and mapping.yaml.
Output: lab.xml, src/, slides/, extra/, manifest.json per lab; _lectures/<topic>/; _course/*.md.
Flow:   load_mapping reads the packaged yaml; lecture_files and course_info_pages locate the
        English files of the clone; build_lab writes one lab directory and its manifest, copying
        the mapped lecture and external files, unpacking the text code files of every zip
        attachment into src/<zip-stem>/ and extracting a .txt sidecar for every pdf.
"""

import hashlib
import shutil
import zipfile
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from rag_lab_generator.ingestion.lab_xml import write_lab_xml
from rag_lab_generator.ingestion.parsers.pdf import write_sidecar
from rag_lab_generator.ingestion.parsers.shortcodes import lang_of
from rag_lab_generator.models import CodeFile, Course, LabDocument, LabManifest, SourceRef

MAPPING_RESOURCE = "mapping.yaml"
COURSE_EXTRA_DIR = "_extra"
SOP1_LECTURES: tuple[str, ...] = (
    "w1",
    "w2",
    "w4",
    "w5",
    "w6",
    "w7",
    "events",
    "mqueue",
    "pipe",
    "scheduling",
)
COURSE_PAGES: tuple[str, ...] = ("syllabus", "zasady", "materialy", "harmonogram", "project")
CODE_SUFFIXES: frozenset[str] = frozenset(
    {".c", ".h", ".cpp", ".cc", ".py", ".sh", ".json", ".yml", ".yaml", ""}
)
ARCHIVE_SUFFIX = ".zip"
SRC_DIR = "src"
BINARY_PROBE_BYTES = 8192


class LabMapping(BaseModel):
    """Lecture topics and external files supporting one lab."""

    lectures: list[str] = Field(default_factory=list)
    kozlowski: list[str] = Field(default_factory=list)


class CourseMapping(BaseModel):
    """External files that belong to a whole course instead of to one lab."""

    kozlowski: list[str] = Field(default_factory=list)


def read_mapping_file() -> dict[str, Any]:
    """Read the packaged mapping.yaml as raw data."""
    text = resources.files("rag_lab_generator.ingestion").joinpath(MAPPING_RESOURCE).read_text()
    parsed: dict[str, Any] = yaml.safe_load(text)
    return parsed


def load_mapping() -> dict[str, LabMapping]:
    """Read the packaged mapping.yaml into one LabMapping per lab id."""
    return {lab_id: LabMapping(**entry) for lab_id, entry in read_mapping_file()["labs"].items()}


def load_course_mapping() -> dict[str, CourseMapping]:
    """Read the course-wide section of mapping.yaml into one CourseMapping per course."""
    raw = read_mapping_file().get("courses") or {}
    return {course: CourseMapping(**entry) for course, entry in raw.items()}


def lecture_dirs(content_root: Path, course: Course) -> list[tuple[str, Path]]:
    """List (topic, directory) of every English lecture of one course."""
    root = content_root / course.value / "wyk"
    if not root.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.endswith(".old"):
            continue
        if course is Course.SOP1 and path.name not in SOP1_LECTURES:
            continue
        if (path / "index.en.md").is_file() or (path / "_index.en.md").is_file():
            found.append((path.name, path))
    return found


def lecture_index_file(directory: Path) -> Path | None:
    """Return the English index page of a lecture directory."""
    for name in ("_index.en.md", "index.en.md"):
        if (directory / name).is_file():
            return directory / name
    return None


def english_pdfs(directory: Path) -> list[Path]:
    """Select the English pdfs of a lecture directory.

    A pdf referenced by the English index page is kept, one referenced only by the Polish page is
    dropped, and an unreferenced pdf is kept unless a sibling carries an explicit "en" marker.
    """
    pdfs = sorted(p for p in directory.glob("*.pdf"))
    if not pdfs:
        return []
    english = lecture_index_file(directory)
    polish = next(
        (directory / n for n in ("_index.pl.md", "index.pl.md") if (directory / n).is_file()), None
    )
    english_text = english.read_text(encoding="utf-8", errors="replace") if english else ""
    polish_text = polish.read_text(encoding="utf-8", errors="replace") if polish else ""
    marked = {p.name for p in pdfs if _has_en_marker(p.name)}

    kept: list[Path] = []
    for pdf in pdfs:
        if pdf.name in english_text:
            kept.append(pdf)
        elif pdf.name in polish_text:
            continue
        elif _has_en_marker(pdf.name) or not _twin_marked(pdf.name, marked):
            kept.append(pdf)
    return kept


def _has_en_marker(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered for token in ("_en_", "_en.", "en_", "-en.", "-en_")
    ) or lowered.startswith("ops1_")


def _twin_marked(name: str, marked: set[str]) -> bool:
    """Tell whether a differently named sibling of the same lecture carries an en marker."""
    stem = name.split("_")[0].split(".")[0].lower()
    return any(other.lower().startswith(stem) for other in marked)


def course_info_pages(
    content_root: Path, repo_root: Path, course: Course
) -> list[tuple[str, Path]]:
    """List (name, path) of the English course information pages of one course."""
    pages: list[tuple[str, Path]] = []
    index = content_root / course.value / "_index.en.md"
    if index.is_file():
        pages.append(("index", index))
    for name in COURSE_PAGES:
        path = content_root / course.value / f"{name}.en.md"
        if path.is_file():
            pages.append((name, path))
    regulamin = repo_root / f"regulamin-{course.value}-en.md"
    if regulamin.is_file():
        pages.append(("regulamin", regulamin))
    return pages


def copy_lecture_tree(directory: Path, target: Path) -> list[str]:
    """Copy one lecture directory into data/raw/<course>/_lectures/<topic>/ and extract pdfs."""
    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    index = lecture_index_file(directory)
    if index is not None:
        shutil.copyfile(index, target / "index.md")
        written.append("index.md")
    slides = directory / "slides" / "index.en.md"
    if slides.is_file():
        shutil.copyfile(slides, target / "slides.md")
        written.append("slides.md")
    code_dir = directory / "code"
    if code_dir.is_dir():
        for path in sorted(code_dir.rglob("*")):
            if not path.is_file() or path.name.endswith((".en.md", ".pl.md")):
                continue
            if path.suffix.lower() not in CODE_SUFFIXES:
                continue
            destination = target / "code" / path.relative_to(code_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            written.append(f"code/{path.relative_to(code_dir).as_posix()}")
    for pdf in english_pdfs(directory):
        shutil.copyfile(pdf, target / pdf.name)
        write_sidecar(target / pdf.name)
        written.extend([pdf.name, f"{pdf.stem}.txt"])
    return written


def _copy_with_sidecar(source: Path, target_dir: Path, name: str | None = None) -> list[str]:
    """Copy one file into target_dir, adding a .txt sidecar when it is a pdf."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (name or source.name)
    shutil.copyfile(source, target)
    written = [target.name]
    if target.suffix.lower() == ".pdf":
        sidecar = target.with_suffix(".txt")
        sibling = source.with_suffix(".txt")
        if sibling.is_file():
            shutil.copyfile(sibling, sidecar)
        else:
            write_sidecar(target)
        written.append(sidecar.name)
    return written


def build_lab(
    lab: LabDocument,
    raw_dir: Path,
    file_index: dict[str, Path],
    external_dir: Path,
    mapping: LabMapping,
) -> LabManifest:
    """Write one lab directory (lab.xml, src/, slides/, extra/, manifest.json)."""
    lab_dir = raw_dir / lab.course.value / lab.slug
    (lab_dir / SRC_DIR).mkdir(parents=True, exist_ok=True)

    sources: list[SourceRef] = []
    src_names: list[str] = []
    unpacked: list[CodeFile] = []
    for code_file in lab.code_files:
        target = lab_dir / code_file.ref
        origin = file_index.get(Path(code_file.ref).name)
        if origin is not None:
            shutil.copyfile(origin, target)
        elif code_file.content:
            target.write_text(code_file.content, encoding="utf-8")
        else:
            continue
        src_names.append(src_name(code_file.ref))
        sources.append(
            SourceRef(url=code_file.source_url or "", local_path=str(target), sha256=sha256(target))
        )
        if target.suffix.lower() == ARCHIVE_SUFFIX:
            unpacked.extend(unpack_attachment(target, lab_dir, code_file.source_url))
    for code_file in unpacked:
        target = lab_dir / code_file.ref
        src_names.append(src_name(code_file.ref))
        sources.append(
            SourceRef(url=code_file.source_url or "", local_path=str(target), sha256=sha256(target))
        )
    lab = lab.model_copy(update={"code_files": [*lab.code_files, *unpacked]})
    write_lab_xml(lab, lab_dir / "lab.xml")

    slide_names: list[str] = []
    for topic in mapping.lectures:
        topic_course, _, topic_name = topic.partition("/")
        source_dir = raw_dir / topic_course / "_lectures" / topic_name
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}:
                slide_names.extend(
                    _copy_with_sidecar(
                        path, lab_dir / "slides", f"{topic_course}_{topic_name}__{path.name}"
                    )
                )

    extra_names: list[str] = []
    for relative in mapping.kozlowski:
        origin = external_dir / "kozlowski" / relative
        if origin.is_file():
            extra_names.extend(_copy_with_sidecar(origin, lab_dir / "extra"))

    manifest = LabManifest(
        lab_id=lab.id,
        course=lab.course,
        slug=lab.slug,
        sources=sources,
        slides=sorted(set(slide_names)),
        extra=sorted(set(extra_names)),
        src=sorted(set(src_names)),
    )
    (lab_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def src_name(ref: str) -> str:
    """Strip the src/ prefix of a code file ref for the manifest."""
    return ref.removeprefix(f"{SRC_DIR}/")


def unpack_attachment(archive: Path, lab_dir: Path, source_url: str | None) -> list[CodeFile]:
    """Extract the text code files of one zip attachment into src/<zip-stem>/ and describe them.

    A single top-level directory inside the archive is dropped, binaries (compiled helpers shipped
    next to the sources) and files outside CODE_SUFFIXES are skipped.
    """
    target_root = lab_dir / SRC_DIR / archive.stem
    unpacked: list[CodeFile] = []
    with zipfile.ZipFile(archive) as bundle:
        members = [info for info in bundle.infolist() if not info.is_dir()]
        prefix = _common_top_level(member.filename for member in members)
        for member in sorted(members, key=lambda info: info.filename):
            relative = Path(member.filename.removeprefix(prefix))
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if relative.suffix.lower() not in CODE_SUFFIXES:
                continue
            data = bundle.read(member)
            if b"\0" in data[:BINARY_PROBE_BYTES]:
                continue
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            unpacked.append(
                CodeFile(
                    ref=f"{SRC_DIR}/{archive.stem}/{relative.as_posix()}",
                    lang=lang_of(relative.name),
                    content=data.decode("utf-8", errors="replace"),
                    source_url=source_url,
                )
            )
    return unpacked


def _common_top_level(names: Iterable[str]) -> str:
    """Return "<dir>/" when every archive member sits under one directory, else ""."""
    listed = list(names)
    heads = {name.split("/", 1)[0] for name in listed if "/" in name}
    if len(heads) != 1 or any("/" not in name for name in listed):
        return ""
    return f"{heads.pop()}/"


def build_course_extra(course_dir: Path, external_dir: Path, mapping: CourseMapping) -> list[str]:
    """Copy the course-wide external material into data/raw/<course>/_extra/."""
    written: list[str] = []
    for relative in mapping.kozlowski:
        origin = external_dir / "kozlowski" / relative
        if origin.is_file():
            written.extend(_copy_with_sidecar(origin, course_dir / COURSE_EXTRA_DIR))
    return sorted(set(written))


def extract_external_sidecars(external_dir: Path, force: bool = False) -> list[Path]:
    """Write a .txt sidecar next to every downloaded pdf so the text is always available."""
    written: list[Path] = []
    for pdf in sorted((external_dir / "kozlowski").rglob("*.pdf")):
        if force or not pdf.with_suffix(".txt").is_file():
            written.append(write_sidecar(pdf))
    return written


def build_file_index(content_root: Path, static_files: Path) -> dict[str, Path]:
    """Index every clone file by base name so lab sources can be copied without rescanning."""
    index: dict[str, Path] = {}
    for path in sorted(content_root.rglob("*")):
        if path.is_file():
            index.setdefault(path.name, path)
    for path in sorted(static_files.glob("*")):
        if path.is_file():
            index[path.name] = path
    return index


def sha256(path: Path) -> str:
    """Hash one file for the lab manifest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
