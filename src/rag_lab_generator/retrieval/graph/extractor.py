"""
Role:   Deterministic knowledge-graph extraction from ingested documents and their chunks.
Input:  list[Document] (labs, lectures, summaries, external pages) and list[Chunk] of one strategy.
Output: (list[GraphNode], list[GraphEdge]) ready for GraphStore.replace_graph.
Flow:   Index chunks by document, section, task and code ref; walk every LabDocument to emit
        course/lab/section/task/code_file nodes with their CONTAINS, RELATED_TO and SOLVED_BY
        edges (a task is RELATED_TO the code unpacked from its zip attachments); emit one
        LECTURE node per non-lab document; scan the text of every section, task
        and lecture with call/man regexes and a curated concept vocabulary to emit API_FUNCTION
        nodes (only for identifiers real code calls or a lab declares) and CONCEPT nodes with
        weighted USES_API / COVERS_CONCEPT edges; finally link labs to
        their lectures, to the previous lab of the course order and to labs sharing topics.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_lab_generator.models import (
    Chunk,
    Course,
    Document,
    DocumentKind,
    EdgeKind,
    GraphEdge,
    GraphNode,
    LabDocument,
    NodeKind,
    Task,
)

ARCHIVE_SUFFIX = ".zip"

# Curated OS-course vocabulary; matched case-insensitively with word boundaries.
CONCEPT_VOCABULARY: tuple[str, ...] = (
    "address space",
    "asynchronous io",
    "atomic operation",
    "barrier",
    "blocking io",
    "busy waiting",
    "cgroup",
    "concurrency",
    "condition variable",
    "container",
    "context switch",
    "critical section",
    "daemon",
    "datagram",
    "deadlock",
    "detached thread",
    "dining philosophers",
    "directory entry",
    "docker image",
    "environment variable",
    "epoll",
    "errno",
    "event loop",
    "exec",
    "exit status",
    "fifo",
    "file descriptor",
    "file offset",
    "file system",
    "fork",
    "hard link",
    "inode",
    "ip address",
    "job control",
    "joinable thread",
    "memory barrier",
    "memory mapping",
    "message queue",
    "mmap",
    "mutex",
    "named pipe",
    "namespace",
    "netcat",
    "non-blocking io",
    "orphan process",
    "page fault",
    "paging",
    "pipe",
    "poll",
    "port number",
    "priority inversion",
    "process group",
    "producer consumer",
    "readers writers",
    "redirection",
    "sanitizer",
    "scheduling",
    "select",
    "semaphore",
    "session",
    "shared memory",
    "signal",
    "signal handler",
    "signal mask",
    "socket",
    "spinlock",
    "spurious wakeup",
    "standard error",
    "standard input",
    "standard output",
    "starvation",
    "stream socket",
    "symbolic link",
    "synchronization",
    "system call",
    "tcp",
    "thread",
    "thread pool",
    "time slice",
    "udp",
    "valgrind",
    "virtual memory",
    "working directory",
    "zombie process",
)

# C keywords, formatting helpers and prose noise that the call regex would otherwise pick up.
API_STOPWORDS: frozenset[str] = frozenset(
    {
        "and",
        "any",
        "assert",
        "bool",
        "break",
        "case",
        "char",
        "cin",
        "const",
        "continue",
        "cout",
        "default",
        "define",
        "defined",
        "double",
        "else",
        "endif",
        "endl",
        "enum",
        "etc",
        "extern",
        "false",
        "float",
        "for",
        "fprintf",
        "from",
        "func",
        "function",
        "functions",
        "get",
        "goto",
        "how",
        "ifdef",
        "ifndef",
        "include",
        "inline",
        "int",
        "long",
        "main",
        "new",
        "not",
        "note",
        "null",
        "one",
        "printf",
        "pragma",
        "program",
        "programs",
        "putchar",
        "puts",
        "register",
        "return",
        "run",
        "scanf",
        "see",
        "set",
        "short",
        "signed",
        "sizeof",
        "snprintf",
        "sprintf",
        "sscanf",
        "static",
        "str",
        "struct",
        "switch",
        "that",
        "the",
        "this",
        "true",
        "two",
        "type",
        "types",
        "typedef",
        "union",
        "unsigned",
        "use",
        "using",
        "value",
        "values",
        "void",
        "volatile",
        "what",
        "when",
        "where",
        "which",
        "while",
        "why",
        "with",
        # prose words a pdf puts before a parenthesis; real posix calls stay out of this list
        "above",
        "again",
        "also",
        "another",
        "are",
        "before",
        "below",
        "between",
        "both",
        "can",
        "cases",
        "chapter",
        "contents",
        "data",
        "during",
        "each",
        "either",
        "every",
        "figure",
        "file",
        "files",
        "first",
        "following",
        "here",
        "information",
        "into",
        "last",
        "line",
        "lines",
        "list",
        "lists",
        "many",
        "model",
        "more",
        "most",
        "name",
        "names",
        "next",
        "number",
        "numbers",
        "once",
        "only",
        "order",
        "other",
        "over",
        "own",
        "page",
        "part",
        "parts",
        "point",
        "points",
        "process",
        "processes",
        "result",
        "results",
        "same",
        "section",
        "sections",
        "size",
        "some",
        "such",
        "systems",
        "table",
        "task",
        "tasks",
        "than",
        "then",
        "there",
        "they",
        "under",
        "user",
        "users",
        "very",
        "way",
        "ways",
        "you",
        "your",
    }
)

# Global lab order; consecutive labs present in the corpus are chained with PREREQUISITE_OF.
LAB_ORDER: tuple[str, ...] = ("l0", "l1", "l2", "l3", "l4", "l5", "l5_5", "l6", "l7", "l8")

_API_CALL_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")
_MAN_PAGE_RE = re.compile(r"\bman\s+\d\w*\s+(\w+)")
# A real call has no space before the parenthesis; prose writes "page (see ...)".
_CODE_CALL_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\(")
_FENCED_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
# Documents whose whole body is source code rather than prose.
CODE_DOCUMENT_KINDS: frozenset[DocumentKind] = frozenset({DocumentKind.LECTURE_CODE})
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{2,}$")
# Word-bounded, case-insensitive, tolerating a plural "s" ("pipes", "file descriptors").
_CONCEPT_RES: dict[str, re.Pattern[str]] = {
    concept: re.compile(rf"(?<!\w){re.escape(concept)}s?(?!\w)", re.IGNORECASE)
    for concept in CONCEPT_VOCABULARY
}

MIN_SHARED_TERMS = 3


def course_node_id(course: str) -> str:
    return f"course:{course}"


def section_node_id(lab_id: str, section_id: str) -> str:
    return f"{lab_id}#section:{section_id}"


def task_node_id(lab_id: str, task_id: str) -> str:
    return f"{lab_id}#task:{task_id}"


def code_node_id(lab_id: str, ref: str) -> str:
    return f"{lab_id}#code:{ref}"


def api_node_id(name: str) -> str:
    return f"api:{name.lower()}"


def concept_node_id(label: str) -> str:
    return f"concept:{label.lower()}"


@dataclass(frozen=True)
class _TextUnit:
    """One piece of prose that API functions and concepts are detected in."""

    node_id: str
    text: str


class _ChunkIndex:
    """Lookup tables from chunks to the graph nodes they belong to."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.by_document: dict[str, list[str]] = defaultdict(list)
        self.by_section: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.by_task: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.by_code_ref: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.by_api: dict[str, list[str]] = defaultdict(list)
        self.by_concept: dict[str, list[str]] = defaultdict(list)
        for chunk in sorted(chunks, key=lambda c: c.id):
            self._index_chunk(chunk)

    def _index_chunk(self, chunk: Chunk) -> None:
        self.by_document[chunk.document_id].append(chunk.id)
        if chunk.section_id:
            self.by_section[(chunk.document_id, chunk.section_id)].append(chunk.id)
        task_id = chunk.metadata.get("task_id")
        if isinstance(task_id, str) and task_id:
            self.by_task[(chunk.document_id, task_id)].append(chunk.id)
        ref = chunk.metadata.get("ref")
        if isinstance(ref, str) and ref:
            self.by_code_ref[(chunk.document_id, ref)].append(chunk.id)
        # a chunk owns an api only when it calls it; the bare word "time" is not a mention
        for name in set(_detect_apis(chunk.text)):
            self.by_api[name].append(chunk.id)
        for concept, pattern in _CONCEPT_RES.items():
            if pattern.search(chunk.text):
                self.by_concept[concept].append(chunk.id)


def _lab_position(lab: LabDocument) -> int:
    """Place a lab on the global order from its slug or the last segment of its id."""
    candidates = [lab.slug.lower(), lab.id.rsplit("/", 1)[-1].lower()]
    best = -1
    for candidate in candidates:
        for position, name in enumerate(LAB_ORDER):
            if candidate == name or candidate.startswith(f"{name}_"):
                if best < 0 or len(LAB_ORDER[best]) < len(name):
                    best = position
        if best >= 0:
            return best
    return best


def _normalize_topic(topic: str) -> str:
    return topic.strip().strip("()").strip().lower()


def _task_text(task: Any) -> str:
    parts = [task.title, task.statement, task.notes]
    parts.extend(stage.text for stage in task.stages)
    return "\n".join(part for part in parts if part)


def _code_identifiers(docs: list[Document]) -> set[str]:
    """Collect every identifier called as name( inside real code anywhere in the corpus."""
    names: set[str] = set()

    def scan(text: str) -> None:
        names.update(match.group(1).lower() for match in _CODE_CALL_RE.finditer(text))

    for doc in docs:
        whole_document_is_code = doc.kind in CODE_DOCUMENT_KINDS
        for section in doc.sections:
            if whole_document_is_code:
                scan(section.text)
                continue
            for block in _FENCED_BLOCK_RE.findall(section.text):
                scan(block)
            for span in _INLINE_CODE_RE.findall(section.text):
                scan(span)
        if isinstance(doc, LabDocument):
            for code_file in doc.code_files:
                scan(code_file.content)
            for task in doc.tasks:
                text = _task_text(task)
                for block in _FENCED_BLOCK_RE.findall(text):
                    scan(block)
                for span in _INLINE_CODE_RE.findall(text):
                    scan(span)
    return names - API_STOPWORDS


def _detect_apis(text: str) -> dict[str, int]:
    """Count call-syntax and man-page mentions of plausible api identifiers in one text."""
    counts: dict[str, int] = defaultdict(int)
    for match in _API_CALL_RE.finditer(text):
        name = match.group(1).lower()
        if name not in API_STOPWORDS:
            counts[name] += 1
    for match in _MAN_PAGE_RE.finditer(text):
        name = match.group(1).lower()
        if _IDENTIFIER_RE.match(name) and name not in API_STOPWORDS:
            counts[name] += 1
    return dict(counts)


def _detect_concepts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for concept, pattern in _CONCEPT_RES.items():
        hits = len(pattern.findall(text))
        if hits:
            counts[concept] = hits
    return counts


class _GraphBuffer:
    """Accumulates nodes and edges, keeping one entry per id / (src, dst, kind)."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[tuple[str, str, EdgeKind], GraphEdge] = {}

    def add_node(self, node: GraphNode) -> GraphNode:
        existing = self.nodes.get(node.id)
        if existing is not None:
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, src: str, dst: str, kind: EdgeKind, weight: float = 1.0) -> None:
        if src == dst or src not in self.nodes or dst not in self.nodes:
            return
        key = (src, dst, kind)
        current = self.edges.get(key)
        if current is None or weight > current.weight:
            self.edges[key] = GraphEdge(src=src, dst=dst, kind=kind, weight=weight)


def extract_graph(
    docs: list[Document], chunks: list[Chunk]
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build the whole knowledge graph from documents and the chunks of one chunking strategy."""
    index = _ChunkIndex(chunks)
    buffer = _GraphBuffer()
    labs = sorted((d for d in docs if isinstance(d, LabDocument)), key=lambda d: d.id)
    others = sorted((d for d in docs if not isinstance(d, LabDocument)), key=lambda d: d.id)
    units: list[_TextUnit] = []
    lab_topics: dict[str, list[str]] = {}

    for course in sorted({d.course.value for d in docs}):
        buffer.add_node(
            GraphNode(
                id=course_node_id(course),
                kind=NodeKind.COURSE,
                label=course,
                course=Course(course),
            )
        )

    for lab in labs:
        lab_topics[lab.id] = [_normalize_topic(t) for t in lab.topics if _normalize_topic(t)]
        _add_lab(buffer, index, lab, units)
    for doc in others:
        _add_lecture(buffer, index, doc, units)

    _add_terminology(buffer, index, units, lab_topics, _code_identifiers(docs))
    _add_lab_links(buffer, labs, others)

    nodes = [buffer.nodes[key] for key in sorted(buffer.nodes)]
    edges = [buffer.edges[key] for key in sorted(buffer.edges, key=lambda k: (k[0], k[1], k[2]))]
    return nodes, edges


def _add_lab(
    buffer: _GraphBuffer, index: _ChunkIndex, lab: LabDocument, units: list[_TextUnit]
) -> None:
    """Emit the lab node with its sections, tasks and code files plus their CONTAINS edges."""
    lab_node = buffer.add_node(
        GraphNode(
            id=lab.id,
            kind=NodeKind.LAB,
            label=lab.title,
            course=lab.course,
            lab_id=lab.id,
            document_id=lab.id,
            properties={"number": lab.number, "slug": lab.slug, "topics": list(lab.topics)},
        )
    )
    buffer.add_edge(course_node_id(lab.course.value), lab.id, EdgeKind.CONTAINS)

    for code_file in sorted(lab.code_files, key=lambda c: c.ref):
        _ensure_code_node(buffer, index, lab, code_file.ref, code_file.lang)

    for section in sorted(lab.sections, key=lambda s: (s.order, s.id)):
        node_id = section_node_id(lab.id, section.id)
        buffer.add_node(
            GraphNode(
                id=node_id,
                kind=NodeKind.SECTION,
                label=section.title,
                course=lab.course,
                lab_id=lab.id,
                document_id=lab.id,
                chunk_ids=list(index.by_section.get((lab.id, section.id), [])),
                properties={"level": section.level, "order": section.order, "slug": section.id},
            )
        )
        buffer.add_edge(lab.id, node_id, EdgeKind.CONTAINS)
        for ref in sorted(set(section.code_refs)):
            code_id = _ensure_code_node(buffer, index, lab, ref, "c")
            buffer.add_edge(node_id, code_id, EdgeKind.RELATED_TO)
        units.append(_TextUnit(node_id=node_id, text=section.text))

    # parent links are resolved after every section node of the lab exists
    for section in lab.sections:
        if section.parent_id:
            buffer.add_edge(
                section_node_id(lab.id, section.parent_id),
                section_node_id(lab.id, section.id),
                EdgeKind.CONTAINS,
            )

    for task in sorted(lab.tasks, key=lambda t: t.id):
        node_id = task_node_id(lab.id, task.id)
        buffer.add_node(
            GraphNode(
                id=node_id,
                kind=NodeKind.TASK,
                label=task.title,
                course=lab.course,
                lab_id=lab.id,
                document_id=lab.id,
                chunk_ids=list(index.by_task.get((lab.id, task.id), [])),
                properties={"task_id": task.id, "stages": len(task.stages)},
            )
        )
        buffer.add_edge(lab.id, node_id, EdgeKind.CONTAINS)
        for ref in sorted(set(task.solution_refs)):
            code_id = _ensure_code_node(buffer, index, lab, ref, "c")
            buffer.add_edge(node_id, code_id, EdgeKind.SOLVED_BY)
        for ref in _attachment_code_refs(lab, task):
            buffer.add_edge(node_id, code_node_id(lab.id, ref), EdgeKind.RELATED_TO)
        units.append(_TextUnit(node_id=node_id, text=_task_text(task)))

    # the lab keeps only the chunks no section, task or code node of this lab already owns
    claimed = {
        chunk_id
        for node in buffer.nodes.values()
        if node.lab_id == lab.id and node.kind is not NodeKind.LAB
        for chunk_id in node.chunk_ids
    }
    lab_node.chunk_ids = [c for c in index.by_document.get(lab.id, []) if c not in claimed]


def _attachment_code_refs(lab: LabDocument, task: Task) -> list[str]:
    """List the code files unpacked from the zip attachments of one task (src/<zip-stem>/...)."""
    prefixes = tuple(
        f"src/{Path(ref).stem}/" for ref in task.attachments if ref.endswith(ARCHIVE_SUFFIX)
    )
    if not prefixes:
        return []
    return sorted(code.ref for code in lab.code_files if code.ref.startswith(prefixes))


def _ensure_code_node(
    buffer: _GraphBuffer, index: _ChunkIndex, lab: LabDocument, ref: str, lang: str
) -> str:
    node_id = code_node_id(lab.id, ref)
    buffer.add_node(
        GraphNode(
            id=node_id,
            kind=NodeKind.CODE_FILE,
            label=ref,
            course=lab.course,
            lab_id=lab.id,
            document_id=lab.id,
            chunk_ids=list(index.by_code_ref.get((lab.id, ref), [])),
            properties={"ref": ref, "lang": lang},
        )
    )
    return node_id


def _add_lecture(
    buffer: _GraphBuffer, index: _ChunkIndex, doc: Document, units: list[_TextUnit]
) -> None:
    buffer.add_node(
        GraphNode(
            id=doc.id,
            kind=NodeKind.LECTURE,
            label=doc.title,
            course=doc.course,
            lab_id=doc.lab_id,
            document_id=doc.id,
            chunk_ids=list(index.by_document.get(doc.id, [])),
            properties={"document_kind": doc.kind.value, "lang": doc.lang},
        )
    )
    buffer.add_edge(course_node_id(doc.course.value), doc.id, EdgeKind.CONTAINS)
    units.append(_TextUnit(node_id=doc.id, text=doc.text))


def _add_terminology(
    buffer: _GraphBuffer,
    index: _ChunkIndex,
    units: list[_TextUnit],
    lab_topics: dict[str, list[str]],
    code_identifiers: set[str],
) -> None:
    """Detect api functions and concepts in every text unit and wire the USES_API edges."""
    api_hits: dict[str, dict[str, int]] = defaultdict(dict)
    concept_hits: dict[str, dict[str, int]] = defaultdict(dict)
    for unit in units:
        for name, count in _detect_apis(unit.text).items():
            api_hits[name][unit.node_id] = count
        for concept, count in _detect_concepts(unit.text).items():
            concept_hits[concept][unit.node_id] = count

    topic_apis: set[str] = set()
    topic_concepts: dict[str, list[str]] = defaultdict(list)
    for lab_id, topics in lab_topics.items():
        for topic in topics:
            if topic in _CONCEPT_RES:
                topic_concepts[topic].append(lab_id)
            elif _IDENTIFIER_RE.match(topic) and topic not in API_STOPWORDS:
                topic_apis.add(topic)

    # an identifier becomes an api node only when real code calls it or a lab declares it
    kept_apis = {n for n in api_hits if n in code_identifiers} | topic_apis
    kept_concepts = set(concept_hits) | set(topic_concepts)

    for name in sorted(kept_apis):
        buffer.add_node(
            GraphNode(
                id=api_node_id(name),
                kind=NodeKind.API_FUNCTION,
                label=name,
                chunk_ids=list(index.by_api.get(name, [])),
                properties={"places": len(api_hits.get(name, {}))},
            )
        )
    for concept in sorted(kept_concepts):
        buffer.add_node(
            GraphNode(
                id=concept_node_id(concept),
                kind=NodeKind.CONCEPT,
                label=concept,
                chunk_ids=list(index.by_concept.get(concept, [])),
                properties={"places": len(concept_hits.get(concept, {}))},
            )
        )

    for name in sorted(kept_apis):
        for unit_id, count in sorted(api_hits.get(name, {}).items()):
            buffer.add_edge(unit_id, api_node_id(name), EdgeKind.USES_API, float(count))
    for concept in sorted(kept_concepts):
        for unit_id, count in sorted(concept_hits.get(concept, {}).items()):
            buffer.add_edge(
                unit_id, concept_node_id(concept), EdgeKind.COVERS_CONCEPT, float(count)
            )

    # topics declared on a lab attach the terminology to the lab itself
    for lab_id, topics in sorted(lab_topics.items()):
        for topic in topics:
            if topic in topic_concepts:
                buffer.add_edge(lab_id, concept_node_id(topic), EdgeKind.COVERS_CONCEPT)
            elif topic in kept_apis:
                buffer.add_edge(lab_id, api_node_id(topic), EdgeKind.USES_API)


def _add_lab_links(buffer: _GraphBuffer, labs: list[LabDocument], others: list[Document]) -> None:
    """Link labs to their lectures, to the previous lab of the course order and to similar labs."""
    for doc in others:
        if doc.lab_id:
            buffer.add_edge(doc.lab_id, doc.id, EdgeKind.COVERED_BY_LECTURE)

    ordered = sorted((lab for lab in labs if _lab_position(lab) >= 0), key=_lab_position)
    for previous, following in zip(ordered, ordered[1:], strict=False):
        buffer.add_edge(previous.id, following.id, EdgeKind.PREREQUISITE_OF)

    terms = _lab_term_sets(buffer, labs)
    lab_ids = sorted(terms)
    for i, left in enumerate(lab_ids):
        for right in lab_ids[i + 1 :]:
            shared = terms[left] & terms[right]
            if len(shared) < MIN_SHARED_TERMS:
                continue
            union = terms[left] | terms[right]
            buffer.add_edge(left, right, EdgeKind.RELATED_TO, len(shared) / len(union))


def _lab_term_sets(buffer: _GraphBuffer, labs: list[LabDocument]) -> dict[str, set[str]]:
    """Collect the api/concept nodes every lab reaches through its own sections and tasks."""
    owner: dict[str, str] = {}
    for lab in labs:
        owner[lab.id] = lab.id
    for node in buffer.nodes.values():
        if node.kind in (NodeKind.SECTION, NodeKind.TASK) and node.lab_id:
            owner[node.id] = node.lab_id
    terms: dict[str, set[str]] = defaultdict(set)
    for edge in buffer.edges.values():
        if edge.kind not in (EdgeKind.USES_API, EdgeKind.COVERS_CONCEPT):
            continue
        lab_id = owner.get(edge.src)
        if lab_id is not None:
            terms[lab_id].add(edge.dst)
    return dict(terms)
