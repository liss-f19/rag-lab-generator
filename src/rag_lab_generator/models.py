"""
Role:   Shared pydantic data contracts crossing every layer boundary.
Input:  none
Output: Model classes and enums imported by ingestion, retrieval, generation, agent and eval.
Flow:   Declares enums for courses/kinds, document models (Document, LabDocument), chunk and
        retrieval models, graph models, LLM message models and eval models. No logic beyond
        light validation and convenience properties.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Course(StrEnum):
    SOP1 = "sop1"
    SOP2 = "sop2"
    EXTERNAL = "external"


class DocumentKind(StrEnum):
    LAB = "lab"
    LECTURE_PDF = "lecture_pdf"
    LECTURE_SLIDES = "lecture_slides"
    LECTURE_INDEX = "lecture_index"
    LECTURE_CODE = "lecture_code"
    COURSE_INFO = "course_info"
    EXTERNAL_PDF = "external_pdf"
    SUMMARY = "summary"


class ChunkKind(StrEnum):
    TUTORIAL = "tutorial"
    TASK = "task"
    CODE = "code"
    LECTURE = "lecture"
    INFO = "info"
    SUMMARY = "summary"


class NodeKind(StrEnum):
    COURSE = "course"
    LAB = "lab"
    SECTION = "section"
    TASK = "task"
    API_FUNCTION = "api_function"
    CONCEPT = "concept"
    LECTURE = "lecture"
    CODE_FILE = "code_file"


class EdgeKind(StrEnum):
    CONTAINS = "contains"
    USES_API = "uses_api"
    COVERS_CONCEPT = "covers_concept"
    PREREQUISITE_OF = "prerequisite_of"
    RELATED_TO = "related_to"
    COVERED_BY_LECTURE = "covered_by_lecture"
    SOLVED_BY = "solved_by"


# ---------------------------------------------------------------- ingestion


class SourceRef(BaseModel):
    """Provenance of one fetched file."""

    url: str
    local_path: str
    sha256: str | None = None
    fetched_at: datetime = Field(default_factory=datetime.now)


class CodeFile(BaseModel):
    ref: str = Field(description="path relative to the lab folder, e.g. src/prog12.c")
    lang: str = "c"
    content: str = ""
    source_url: str | None = None


class Section(BaseModel):
    id: str = Field(description="slug unique inside the document, e.g. browsing-a-directory")
    title: str
    level: int = 2
    order: int = 0
    text: str = Field(description="markdown body with shortcodes expanded")
    code_refs: list[str] = Field(default_factory=list)
    parent_id: str | None = None


class Stage(BaseModel):
    n: int
    text: str


class Task(BaseModel):
    id: str = Field(description="e.g. example1")
    title: str
    statement: str
    stages: list[Stage] = Field(default_factory=list)
    solution_refs: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    notes: str = ""
    source_url: str | None = None


class Reference(BaseModel):
    url: str
    title: str = ""


class Document(BaseModel):
    """Any ingested unit: lecture pdf, slides deck, course info page, external pdf."""

    id: str = Field(description="stable id, e.g. sop1/lecture/w2/OPS1_Filesystem_API")
    course: Course
    kind: DocumentKind
    title: str
    lang: str = "en"
    source_url: str | None = None
    local_path: str | None = None
    lab_id: str | None = Field(default=None, description="owning lab id when attached to a lab")
    sections: list[Section] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(s.text for s in self.sections)


class LabDocument(Document):
    """A laboratory page: tutorial sections, example tasks, source files."""

    kind: DocumentKind = DocumentKind.LAB
    number: str = Field(description="lab number as on the site: 1, 5.5, netcat")
    slug: str = Field(description="folder name, e.g. l1_filesystem")
    topics: list[str] = Field(default_factory=list, description="api functions / concepts")
    tasks: list[Task] = Field(default_factory=list)
    code_files: list[CodeFile] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)


class LabManifest(BaseModel):
    """manifest.json written next to lab.xml."""

    lab_id: str
    course: Course
    slug: str
    generated_at: datetime = Field(default_factory=datetime.now)
    sources: list[SourceRef] = Field(default_factory=list)
    slides: list[str] = Field(default_factory=list, description="files copied into slides/")
    extra: list[str] = Field(default_factory=list, description="files copied into extra/")
    src: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- chunks and retrieval


class Chunk(BaseModel):
    id: str = Field(description="<strategy>:<document_id>:<idx>")
    document_id: str
    course: Course
    lab_id: str | None = None
    kind: ChunkKind
    strategy: str
    idx: int
    text: str
    char_count: int = 0
    parent_id: str | None = None
    section_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.char_count == 0:
            self.char_count = len(self.text)


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float
    source: str = Field(description="searcher that produced the score")


class RetrievedContext(BaseModel):
    query: str
    rag: str
    chunks: list[ScoredChunk]
    trace: dict[str, Any] = Field(default_factory=dict, description="graph paths, timings")

    def as_prompt_text(self, max_chars: int | None = None) -> str:
        parts: list[str] = []
        total = 0
        for sc in self.chunks:
            label = sc.chunk.section_id or sc.chunk.kind
            block = f"[{sc.chunk.document_id} / {label}]\n{sc.chunk.text}"
            if max_chars is not None and total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------- graph


class GraphNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    course: Course | None = None
    lab_id: str | None = None
    document_id: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: EdgeKind
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- generation


class LLMMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


class GeneratedLab(BaseModel):
    title: str
    course: Course
    based_on: list[str] = Field(default_factory=list, description="reference lab ids")
    topics: list[str] = Field(default_factory=list)
    description: str
    stages: list[Stage] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


# ---------------------------------------------------------------- eval


class EvalQuery(BaseModel):
    id: str
    query: str
    expected_lab_ids: list[str] = Field(default_factory=list)
    expected_section_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EvalConfig(BaseModel):
    rag: str
    chunker: str
    searcher: str
    embedder: str
    k: int


class EvalMetrics(BaseModel):
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    latency_ms_p50: float
    n_queries: int


class EvalRun(BaseModel):
    config: EvalConfig
    metrics: EvalMetrics
    created_at: datetime = Field(default_factory=datetime.now)
