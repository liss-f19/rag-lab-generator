"""
Role:   Pure retrieval metrics over a ranked chunk list; no database, no io, deterministic.
Input:  The top-k ScoredChunk list of one query plus the EvalQueryFile that describes the gold.
Output: QueryMetrics per query and EvalMetricsFull (EvalMetrics plus the extra columns) per run.
Flow:   relevance_flags() marks every retrieved chunk relevant when its lab or document matches an
        expectation; the scalar functions (hit, recall, mrr, ndcg, coverage) read those flags and
        the covered target sets; context_stats() summarises the prompt payload, including the
        primary/background support mix taken from a document_id -> support map; query_metrics()
        bundles them for one query and aggregate() averages them over a run.
"""

from math import log2

from pydantic import BaseModel, Field

from rag_lab_generator.eval.queries import SECTION_SEPARATOR, EvalQueryFile
from rag_lab_generator.models import Chunk, EvalMetrics, ScoredChunk

UNKNOWN_SUPPORT = "unknown"


class ContextStats(BaseModel):
    """Shape of the context one query would hand to the generator."""

    n_chunks: int = 0
    total_chars: int = 0
    distinct_documents: int = 0
    kinds: dict[str, int] = Field(default_factory=dict)
    support: dict[str, int] = Field(
        default_factory=dict, description="documents.metadata->>support of every chunk"
    )


class QueryMetrics(BaseModel):
    """Every metric of one (config, query) pair."""

    query_id: str
    hit: float = 0.0
    first_relevant_rank: int | None = None
    recall_at_k: float = 0.0
    section_recall_at_k: float | None = None
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    coverage: float = 0.0
    latency_ms: float = 0.0
    context: ContextStats = Field(default_factory=ContextStats)


class EvalMetricsFull(EvalMetrics):
    """EvalMetrics with the columns the thesis table needs next to the contract fields."""

    hit_at_k: float = 0.0
    section_recall_at_k: float = 0.0
    coverage: float = 0.0
    latency_ms_mean: float = 0.0
    latency_ms_p50_warm: float = 0.0
    latency_ms_first: float = Field(
        default=0.0, description="first query: pays for the graph edges and the embedding model"
    )
    context_chars_mean: float = 0.0
    distinct_documents_mean: float = 0.0
    n_section_queries: int = 0
    kind_distribution: dict[str, float] = Field(default_factory=dict)
    support_distribution: dict[str, float] = Field(default_factory=dict)


def matches_target(chunk: Chunk, target: str) -> bool:
    """True when the chunk belongs to the target lab or document (exact id or id prefix)."""
    document_id = chunk.document_id.split("@", 1)[0]
    if target in (chunk.lab_id, document_id):
        return True
    return document_id.startswith(f"{target}/")


def section_key(chunk: Chunk) -> str | None:
    if chunk.section_id is None:
        return None
    return f"{chunk.document_id}{SECTION_SEPARATOR}{chunk.section_id}"


def relevance_flags(chunks: list[ScoredChunk], query: EvalQueryFile) -> list[bool]:
    """One boolean per retrieved chunk: does it belong to an expected lab or document."""
    targets = query.targets
    return [any(matches_target(sc.chunk, target) for target in targets) for sc in chunks]


def covered_targets(chunks: list[ScoredChunk], targets: list[str]) -> set[str]:
    return {t for t in targets if any(matches_target(sc.chunk, t) for sc in chunks)}


def covered_sections(chunks: list[ScoredChunk], expected: list[str]) -> set[str]:
    found = {key for key in (section_key(sc.chunk) for sc in chunks) if key is not None}
    return {key for key in expected if key in found}


def hit_at_k(flags: list[bool]) -> float:
    return 1.0 if any(flags) else 0.0


def first_relevant_rank(flags: list[bool]) -> int | None:
    """1-based rank of the first relevant chunk, None when nothing relevant was retrieved."""
    for position, flag in enumerate(flags, start=1):
        if flag:
            return position
    return None


def mrr(flags: list[bool]) -> float:
    rank = first_relevant_rank(flags)
    return 0.0 if rank is None else 1.0 / rank


def ndcg_at_k(flags: list[bool], k: int) -> float:
    """Binary-gain nDCG; the ideal ranking is k relevant chunks, which the corpus always holds."""
    if k <= 0:
        return 0.0
    dcg = sum(1.0 / log2(position + 1) for position, flag in enumerate(flags[:k], start=1) if flag)
    idcg = sum(1.0 / log2(position + 1) for position in range(1, k + 1))
    return dcg / idcg if idcg else 0.0


def recall_at_k(chunks: list[ScoredChunk], targets: list[str]) -> float:
    """Fraction of expected labs and documents that have at least one chunk in the top k."""
    if not targets:
        return 0.0
    return len(covered_targets(chunks, targets)) / len(targets)


def section_recall_at_k(chunks: list[ScoredChunk], expected: list[str]) -> float | None:
    """Fraction of expected sections present in the top k; None when the query names none."""
    if not expected:
        return None
    return len(covered_sections(chunks, expected)) / len(expected)


def coverage(chunks: list[ScoredChunk], expected_lab_ids: list[str]) -> float:
    """Recall restricted to the expected labs, ignoring expected lecture documents."""
    if not expected_lab_ids:
        return 0.0
    return len(covered_targets(chunks, expected_lab_ids)) / len(expected_lab_ids)


def context_stats(
    chunks: list[ScoredChunk], support_by_document: dict[str, str] | None = None
) -> ContextStats:
    """Size, spread, chunk kinds and support mix of one retrieved context."""
    support_map = support_by_document or {}
    kinds: dict[str, int] = {}
    support: dict[str, int] = {}
    for scored in chunks:
        kinds[scored.chunk.kind.value] = kinds.get(scored.chunk.kind.value, 0) + 1
        label = support_map.get(scored.chunk.document_id, UNKNOWN_SUPPORT)
        support[label] = support.get(label, 0) + 1
    return ContextStats(
        n_chunks=len(chunks),
        total_chars=sum(sc.chunk.char_count for sc in chunks),
        distinct_documents=len({sc.chunk.document_id for sc in chunks}),
        kinds=dict(sorted(kinds.items())),
        support=dict(sorted(support.items())),
    )


def query_metrics(
    chunks: list[ScoredChunk],
    query: EvalQueryFile,
    k: int,
    latency_ms: float = 0.0,
    support_by_document: dict[str, str] | None = None,
) -> QueryMetrics:
    """Every metric of one query over the already truncated top-k list."""
    top = chunks[:k]
    flags = relevance_flags(top, query)
    return QueryMetrics(
        query_id=query.id,
        hit=hit_at_k(flags),
        first_relevant_rank=first_relevant_rank(flags),
        recall_at_k=recall_at_k(top, query.targets),
        section_recall_at_k=section_recall_at_k(top, query.expected_section_ids),
        mrr=mrr(flags),
        ndcg_at_k=ndcg_at_k(flags, k),
        coverage=coverage(top, query.expected_lab_ids),
        latency_ms=latency_ms,
        context=context_stats(top, support_by_document),
    )


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile of an unsorted list; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(results: list[QueryMetrics]) -> EvalMetricsFull:
    """Average the per-query metrics of one configuration into the run-level row."""
    latencies = [r.latency_ms for r in results]
    sections = [r.section_recall_at_k for r in results if r.section_recall_at_k is not None]
    kinds: dict[str, float] = {}
    support: dict[str, float] = {}
    for result in results:
        for kind, count in result.context.kinds.items():
            kinds[kind] = kinds.get(kind, 0.0) + count
        for label, count in result.context.support.items():
            support[label] = support.get(label, 0.0) + count
    total_kinds = sum(kinds.values())
    total_support = sum(support.values())
    return EvalMetricsFull(
        recall_at_k=mean([r.recall_at_k for r in results]),
        mrr=mean([r.mrr for r in results]),
        ndcg_at_k=mean([r.ndcg_at_k for r in results]),
        latency_ms_p50=percentile(latencies, 0.5),
        n_queries=len(results),
        hit_at_k=mean([r.hit for r in results]),
        section_recall_at_k=mean(sections),
        coverage=mean([r.coverage for r in results]),
        latency_ms_mean=mean(latencies),
        latency_ms_p50_warm=percentile(latencies[1:], 0.5),
        latency_ms_first=latencies[0] if latencies else 0.0,
        context_chars_mean=mean([float(r.context.total_chars) for r in results]),
        distinct_documents_mean=mean([float(r.context.distinct_documents) for r in results]),
        n_section_queries=len(sections),
        kind_distribution=(
            {k: v / total_kinds for k, v in sorted(kinds.items())} if total_kinds else {}
        ),
        support_distribution=(
            {k: v / total_support for k, v in sorted(support.items())} if total_support else {}
        ),
    )
