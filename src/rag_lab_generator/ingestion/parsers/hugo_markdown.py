"""
Role:   Parser turning hugo pages of the sop-site clone into Section, Task, Document and
        LabDocument models.
Input:  Paths inside <external>/sop-site/content plus the course and lab slug to assign.
Output: LabDocument for a lab directory, Task for one example page, Document for info pages.
Flow:   Reads front matter with python-frontmatter, expands shortcodes, splits the body on
        headings while keeping fenced blocks intact, derives topics from inline code spans and
        man references, and collects the code files that live next to the page.
"""

import re
from pathlib import Path

import frontmatter

from rag_lab_generator.ingestion.parsers.shortcodes import (
    SITE_BASE_URL,
    ShortcodeResult,
    expand_shortcodes,
    lang_of,
    mask_fences,
    split_fences,
)
from rag_lab_generator.models import (
    CodeFile,
    Course,
    Document,
    DocumentKind,
    LabDocument,
    Reference,
    Section,
    Stage,
    Task,
)

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.M)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
MAN_RE = re.compile(r"\bman\s+\d[a-z]?\s+([A-Za-z_][\w.]*)")
CALL_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")
MACRO_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]{2,}$")
LINK_RE = re.compile(r"\[([^\]\n]*)\]\((https?://[^)\s]+)\)")
STAGE_ITEM_RE = re.compile(r"^[ \t]*(?:\d+[.)]|[-*+])[ \t]+", re.M)

TOPIC_FALLBACK_MIN = 8
STAGES_TITLES = ("stages", "graded stages", "steps", "etapy", "stage")
CODE_SUFFIXES = (".c", ".h", ".cpp", ".sh", ".py", ".txt", ".zip", ".mk")

# Words that pass the identifier shape test but are never a POSIX API name.
TOPIC_STOPWORDS: frozenset[str] = frozenset(
    {
        "and",
        "are",
        "argv",
        "argc",
        "bool",
        "break",
        "buf",
        "case",
        "char",
        "const",
        "continue",
        "double",
        "else",
        "enum",
        "errno",
        "extern",
        "false",
        "float",
        "for",
        "goto",
        "int",
        "long",
        "main",
        "not",
        "null",
        "programs",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "the",
        "this",
        "true",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "with",
        "you",
        "your",
        "file",
        "files",
        "data",
        "code",
        "name",
        "value",
        "size",
        "type",
        "func",
        "function",
        "example",
        "number",
        "string",
        "make",
        "gcc",
        "bash",
        "echo",
        "cat",
        "true_",
        "usr",
        "tmp",
        "etc",
        "var",
        "out",
        "err",
    }
)

LAB_SLUGS: dict[str, str] = {
    "sop1/l0": "l0_posix_environment",
    "sop1/l1": "l1_filesystem",
    "sop1/l2": "l2_processes_signals",
    "sop1/l3": "l3_threads_mutexes_signals",
    "sop1/l4": "l4_synchronization",
    "sop1/sanitizers": "sanitizers",
    "sop2/l5": "l5_fifo_pipe",
    "sop2/l5_5": "l5_5_posix_queues",
    "sop2/l6": "l6_shm_mmap",
    "sop2/l7": "l7_sockets_epoll",
    "sop2/l8": "l8_datagram_servers",
    "sop2/netcat": "netcat",
}


def slugify(text: str) -> str:
    """Reduce a heading to an ascii slug usable as a section id."""
    ascii_text = text.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "section"


def lab_number(hugo_dir: str) -> str:
    """Derive the lab number as shown on the site from the hugo directory name."""
    match = re.fullmatch(r"l(\d+)(?:_(\d+))?", hugo_dir)
    if match is None:
        return hugo_dir
    return f"{match.group(1)}.{match.group(2)}" if match.group(2) else match.group(1)


def page_url(content_relative: Path) -> str:
    """Build the public URL of a hugo page from its path relative to content/."""
    parts = list(content_relative.parts)
    last = parts[-1]
    if last in {"_index.en.md", "index.en.md"}:
        parts = parts[:-1]
    else:
        parts[-1] = last.removesuffix(".en.md")
    return f"{SITE_BASE_URL}/en/{'/'.join(parts)}/".replace("//en/", "/en/")


def read_page(path: Path) -> tuple[dict[str, object], str]:
    """Return (front matter, body) of one hugo markdown file."""
    post = frontmatter.loads(path.read_text(encoding="utf-8", errors="replace"))
    return dict(post.metadata), post.content


def split_sections(body: str, start_order: int = 0) -> list[Section]:
    """Split a markdown body on headings, never cutting inside a fenced code block."""
    scan = mask_fences(body)
    heads = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(scan)]

    spans: list[tuple[int, str, int, int]] = []
    if not heads or heads[0][0] > 0:
        first_end = heads[0][0] if heads else len(body)
        if body[:first_end].strip():
            spans.append((1, "Overview", 0, first_end))
    for idx, (pos, level, title) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(body)
        spans.append((level, title, pos, end))

    sections: list[Section] = []
    used: dict[str, int] = {}
    stack: list[tuple[int, str]] = []
    for order, (level, title, start, end) in enumerate(spans):
        base = slugify(title)
        used[base] = used.get(base, 0) + 1
        section_id = base if used[base] == 1 else f"{base}-{used[base]}"
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_id = stack[-1][1] if stack else None
        stack.append((level, section_id))
        text = body[start:end].strip("\n")
        sections.append(
            Section(
                id=section_id,
                title=title,
                level=level,
                order=start_order + order,
                text=text,
                parent_id=parent_id,
            )
        )
    return sections


def extract_topics(text: str) -> list[str]:
    """Collect POSIX API names and macros mentioned in the text, ordered by first appearance.

    A token is kept when it is an ALL_CAPS macro, or a lowercase identifier that also appears
    somewhere in the page followed by "(" inside code (a fenced block or an inline span), or is
    named by a "man N name" reference. Prose words are therefore never picked up.
    """
    prose = mask_fences(text)
    fenced = "\n".join(chunk for is_code, chunk in split_fences(text) if is_code)
    spans = [(m.start(), m.group(1).strip()) for m in INLINE_CODE_RE.finditer(prose)]
    man_names = [(m.start(), m.group(1)) for m in MAN_RE.finditer(text)]
    code_text = fenced + "\n" + "\n".join(span for _, span in spans)
    called = {m.group(1) for m in CALL_RE.finditer(code_text)}
    called.update(name.split(".")[0] for _, name in man_names)

    found: list[str] = []
    seen: set[str] = set()
    for _, raw in sorted(spans + man_names, key=lambda item: item[0]):
        token = raw.split("(")[0].strip().rstrip(";,.").lstrip("*&")
        if MACRO_RE.fullmatch(token):
            pass
        elif not IDENT_RE.fullmatch(token) or token in TOPIC_STOPWORDS or token not in called:
            continue
        if token not in seen:
            seen.add(token)
            found.append(token)

    # Tutorials that never use inline code spans fall back to the calls of their code blocks.
    if len(found) < TOPIC_FALLBACK_MIN:
        for match in CALL_RE.finditer(fenced):
            token = match.group(1)
            if token not in seen and token not in TOPIC_STOPWORDS:
                seen.add(token)
                found.append(token)
    return found


def extract_references(text: str) -> list[Reference]:
    """Collect outgoing http links with their markdown link text, deduplicated by URL."""
    references: list[Reference] = []
    seen: set[str] = set()
    for match in LINK_RE.finditer(text):
        url = match.group(2).rstrip(".,")
        if url in seen:
            continue
        seen.add(url)
        references.append(Reference(url=url, title=match.group(1).strip()))
    return references


def _stage_heading_index(sections: list[Section]) -> int | None:
    for idx, section in enumerate(sections):
        title = section.title.lower().strip().rstrip(":").strip()
        if title in STAGES_TITLES or title.endswith(" stages") or title.startswith("stages"):
            return idx
    return None


def parse_stages(text: str) -> list[Stage]:
    """Split the body of a stages section into one Stage per list item."""
    body = "\n".join(text.split("\n")[1:]) if text.lstrip().startswith("#") else text
    starts = [m.start() for m in STAGE_ITEM_RE.finditer(body)]
    stages: list[Stage] = []
    for n, start in enumerate(starts, start=1):
        end = starts[n] if n < len(starts) else len(body)
        item = STAGE_ITEM_RE.sub("", body[start:end], count=1).strip()
        if item:
            stages.append(Stage(n=n, text=item))
    if not stages and body.strip():
        stages.append(Stage(n=1, text=body.strip()))
    return stages


def expand_sections(
    sections: list[Section],
    base_dir: Path | None,
    page_dir: str,
    page_url_path: str,
) -> ShortcodeResult:
    """Expand shortcodes inside every section in place and return the merged expansion result."""
    merged = ShortcodeResult(text="")
    for section in sections:
        result = expand_shortcodes(section.text, base_dir, page_dir, page_url_path)
        section.text = result.text.strip("\n")
        section.code_refs = [f"src/{name}" for name in result.code_refs]
        merged.code_refs.extend(result.code_refs)
        merged.resources.extend(result.resources)
        merged.links.extend(result.links)
        merged.answers.extend(result.answers)
        merged.unresolved.extend(result.unresolved)
    merged.text = "\n\n".join(section.text for section in sections)
    return merged


def parse_task(
    path: Path,
    content_root: Path,
    base_dir: Path | None = None,
    task_id: str | None = None,
) -> Task:
    """Parse one example page into a Task (statement, stages, attachments, notes)."""
    relative = path.relative_to(content_root)
    metadata, body = read_page(path)
    sections = split_sections(body)
    expanded = expand_sections(
        sections,
        base_dir if base_dir is not None else path.parent,
        f"content/{relative.parent.as_posix()}",
        relative.parent.as_posix(),
    )
    stages_at = _stage_heading_index(sections)
    if stages_at is None:
        statement = expanded.text.strip()
        stages: list[Stage] = []
    else:
        head = [s.text for s in sections[:stages_at]]
        tail = [s.text for s in sections[stages_at + 1 :]]
        statement = "\n\n".join(part for part in head + tail if part.strip()).strip()
        stages = parse_stages(sections[stages_at].text)

    attachments = [
        f"src/{Path(m.group(2)).name}"
        for m in re.finditer(r"\[([^\]]*)\]\((/files/[^)\s]+)\)", expanded.text)
    ]
    solution_refs = [f"src/{name}" for name in expanded.resources if Path(name).suffix == ".c"]
    title = str(metadata.get("title") or path.stem.removesuffix(".en"))
    return Task(
        id=task_id or path.stem.removesuffix(".en"),
        title=title,
        statement=statement,
        stages=stages,
        solution_refs=sorted(set(solution_refs)),
        attachments=sorted(set(attachments)),
        notes="\n\n".join(expanded.answers).strip(),
        source_url=page_url(relative),
    )


def _task_pages(lab_dir: Path) -> list[tuple[str, Path, Path]]:
    """List (task id, page path, resource dir) of every example page of a lab."""
    pages: list[tuple[str, Path, Path]] = []
    for page in sorted(lab_dir.glob("example*.en.md")):
        pages.append((page.stem.removesuffix(".en"), page, lab_dir))
    for sub in sorted(p for p in lab_dir.iterdir() if p.is_dir()):
        index = sub / "_index.en.md"
        if not index.is_file():
            index = sub / "index.en.md"
        if index.is_file():
            pages.append((sub.name, index, sub))
    return sorted(pages, key=lambda item: item[0])


def collect_code_files(lab_dir: Path) -> list[Path]:
    """List every code or attachment file that belongs to a lab directory (recursively)."""
    return [
        path
        for path in sorted(lab_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in CODE_SUFFIXES
    ]


def parse_lab(
    index_path: Path,
    content_root: Path,
    course: Course,
    hugo_dir: str,
    static_files: Path | None = None,
) -> LabDocument:
    """Parse one lab (tutorial page, example tasks, code files) into a LabDocument."""
    lab_id = f"{course.value}/{hugo_dir}"
    slug = LAB_SLUGS.get(lab_id, hugo_dir)
    lab_dir = index_path.parent
    is_directory_lab = index_path.name in {"_index.en.md", "index.en.md"}
    relative = index_path.relative_to(content_root)
    metadata, body = read_page(index_path)
    sections = split_sections(body)
    expanded = expand_sections(
        sections,
        lab_dir,
        f"content/{relative.parent.as_posix()}",
        relative.parent.as_posix(),
    )

    code_paths = collect_code_files(lab_dir) if is_directory_lab else []
    code_files = [
        CodeFile(
            ref=f"src/{path.name}",
            lang=lang_of(path.name),
            content=path.read_text(encoding="utf-8", errors="replace"),
            source_url=(
                f"{SITE_BASE_URL}/en/{path.relative_to(content_root).parent.as_posix()}/{path.name}"
            ),
        )
        for path in code_paths
    ]
    known = {file.ref for file in code_files}

    tasks = (
        [
            parse_task(page, content_root, base_dir=resource_dir, task_id=task_id)
            for task_id, page, resource_dir in _task_pages(lab_dir)
            if page != index_path
        ]
        if is_directory_lab
        else []
    )
    attachments = {ref for task in tasks for ref in task.attachments}
    if static_files is not None:
        for ref in sorted(attachments):
            candidate = static_files / Path(ref).name
            if candidate.is_file() and ref not in known:
                code_files.append(
                    CodeFile(
                        ref=ref,
                        lang=lang_of(candidate.name),
                        content="",
                        source_url=f"{SITE_BASE_URL}/files/{candidate.name}",
                    )
                )

    title = str(metadata.get("title") or hugo_dir)
    full_text = expanded.text + "\n\n" + "\n\n".join(t.statement for t in tasks)
    return LabDocument(
        id=lab_id,
        course=course,
        title=re.sub(r"^L[\d._]+\s*-\s*", "", title).strip(),
        number=lab_number(hugo_dir),
        slug=slug,
        source_url=page_url(relative),
        sections=sections,
        topics=extract_topics(expanded.text),
        tasks=tasks,
        code_files=code_files,
        references=extract_references(full_text),
    )


def parse_info_page(
    path: Path,
    content_root: Path | None,
    course: Course,
    name: str,
    source_url: str | None = None,
) -> Document:
    """Parse a course information page (syllabus, rules, schedule) into a Document."""
    metadata, body = read_page(path)
    relative = path.relative_to(content_root) if content_root is not None else Path(path.name)
    sections = split_sections(body)
    expand_sections(
        sections,
        path.parent,
        f"content/{relative.parent.as_posix()}",
        relative.parent.as_posix(),
    )
    return Document(
        id=f"{course.value}/course/{name}",
        course=course,
        kind=DocumentKind.COURSE_INFO,
        title=str(metadata.get("title") or name),
        source_url=source_url if source_url is not None else page_url(relative),
        sections=sections,
        metadata={"page": name},
    )
