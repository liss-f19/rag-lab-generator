"""
Role:   Pydantic request and response contracts of the HTTP layer.
Input:  JSON bodies and query parameters of the API; domain models from models.py.
Output: Typed models FastAPI serializes into the JSON the web client consumes.
Flow:   Groups the schemas per router (health, corpus, retrieval, graph, chat, eval); domain
        models (LabDocument, RetrievedContext) are embedded as-is so the UI sees the real
        pipeline output instead of a reduced copy.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rag_lab_generator.models import LabDocument, RetrievedContext

# ---------------------------------------------------------------- health


class HealthResponse(BaseModel):
    """Everything the top bar of the web client needs to describe the running system."""

    version: str
    llm_provider: str
    llm_model: str
    embedding_provider: str
    rag: str
    searcher: str
    chunker: str
    retrieval_k: int
    data_dir: str
    db_reachable: bool
    corpus_present: bool
    agent_available: bool
    graph_available: bool
    strategies: dict[str, list[str]]


class StrategiesResponse(BaseModel):
    kinds: dict[str, list[str]]
    defaults: dict[str, str]


# ---------------------------------------------------------------- corpus


class LabSummary(BaseModel):
    id: str
    course: str
    slug: str
    title: str
    number: str
    n_tasks: int
    n_sections: int
    n_files: int
    has_summary: bool


class CourseSummary(BaseModel):
    course: str
    n_labs: int
    labs: list[LabSummary]


class CoursesResponse(BaseModel):
    data_dir: str
    corpus_present: bool
    courses: list[CourseSummary]


class LabFile(BaseModel):
    path: str = Field(description="path relative to the lab folder, e.g. src/prog1.c")
    group: str = Field(description="src, slides or extra")
    size: int
    media_type: str


class LabDetailResponse(BaseModel):
    lab: LabDocument
    summary: str | None = None
    manifest: dict[str, Any] | None = None
    files: list[LabFile] = Field(default_factory=list)


# ---------------------------------------------------------------- retrieval


class ResolvedConfig(BaseModel):
    """The strategy names actually used, after request values fell back to Settings."""

    rag: str
    searcher: str
    strategy: str
    embedder: str
    k: int


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    rag: str | None = None
    searcher: str | None = None
    strategy: str | None = None
    embedder: str | None = None
    k: int | None = Field(default=None, ge=1, le=50)
    course: str | None = None
    lab_id: str | None = None
    kinds: list[str] | None = None


class RetrieveResponse(BaseModel):
    config: ResolvedConfig
    latency_ms: float
    context: RetrievedContext


class CompareConfig(BaseModel):
    rag: str
    searcher: str


class CompareRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1, le=50)
    strategy: str | None = None
    embedder: str | None = None
    course: str | None = None
    lab_id: str | None = None
    configs: list[CompareConfig] = Field(min_length=1, max_length=4)


class CompareResult(BaseModel):
    config: ResolvedConfig
    latency_ms: float
    context: RetrievedContext | None = None
    error: str | None = None


class CompareResponse(BaseModel):
    query: str
    results: list[CompareResult]


# ---------------------------------------------------------------- graph


class GraphNodeOut(BaseModel):
    id: str
    kind: str
    label: str
    course: str | None = None
    lab_id: str | None = None
    document_id: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    degree: int = 0
    hops: int | None = Field(default=None, description="distance from the queried node")


class GraphEdgeOut(BaseModel):
    src: str
    dst: str
    kind: str
    weight: float = 1.0


class SubgraphResponse(BaseModel):
    center: str | None = None
    hops: int = 1
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class GraphStatsResponse(BaseModel):
    counts: dict[str, int]


class ChunkPreview(BaseModel):
    id: str
    document_id: str
    lab_id: str | None = None
    kind: str
    section_id: str | None = None
    text: str


class NodeDescriptionOut(BaseModel):
    text: str
    model: str
    generated_at: datetime


class NodeSourceLocationOut(BaseModel):
    chunk_id: str
    label: str
    kind: str


class NodeSourceOut(BaseModel):
    document_id: str
    title: str
    kind: str
    course: str
    lab_id: str | None = None
    slug: str | None = None
    locations: list[NodeSourceLocationOut] = Field(default_factory=list)


class NodeChunksResponse(BaseModel):
    node_id: str
    description: NodeDescriptionOut | None = None
    sources: list[NodeSourceOut] = Field(default_factory=list)
    chunks: list[ChunkPreview]


# ---------------------------------------------------------------- chat


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    course: str | None = None
    lab_id: str | None = None
    llm: str | None = None
    rag: str | None = None


class ChatToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: list[ChatToolCall] = Field(default_factory=list)


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: list[ChatMessage]


# ---------------------------------------------------------------- eval


class EvalCsvFile(BaseModel):
    name: str
    path: str
    columns: list[str]
    rows: list[dict[str, str]]


class EvalDbRun(BaseModel):
    id: int
    created_at: datetime
    config: dict[str, Any]
    metrics: dict[str, Any]


class EvalRunsResponse(BaseModel):
    results_dir: str
    db_reachable: bool
    files: list[EvalCsvFile]
    db_runs: list[EvalDbRun]
