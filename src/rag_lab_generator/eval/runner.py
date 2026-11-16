"""
Role:   Strategy-matrix runner: builds every retrieval configuration once, times it over the gold
        set, computes the metrics and persists the results.
Input:  Settings, a list of EvalConfig (EvalConfigSpec carries the graph extras), the gold queries,
        k and an output directory; chunks, embeddings and the graph live in Postgres.
Output: list[EvalRun]; results/eval_<ts>.csv, results/eval_<ts>_per_query.csv,
        results/eval_latest.json and one row per configuration in the eval_runs table.
Flow:   default_matrix() expands the recipes into configurations; run_matrix() reads the corpus
        prerequisites once, skips or downgrades the configurations whose chunks, vectors or graph
        are missing, builds store/embedder/searcher/rag once per configuration, runs every query
        with the same instance, truncates the context to k by score (never comparing scores across
        rags, only ranks inside one context), aggregates the metrics and writes the csv, json and
        database rows.
"""

import csv
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.eval.metrics import QueryMetrics, aggregate, query_metrics
from rag_lab_generator.eval.queries import EvalQueryFile
from rag_lab_generator.models import EvalConfig, EvalRun, RetrievedContext, ScoredChunk
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.stores.graph_store import GraphStore
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

# (rag name, wrapping searcher) - the graph rag always runs through the graph walker so that the
# compared searcher is the walker's seed source, which makes vector and graph rows comparable.
RAG_RECIPES: tuple[tuple[str, str | None], ...] = (("vector", None), ("graph", "graph_walk"))
# (searcher name, does it read embeddings)
SEARCHER_RECIPES: tuple[tuple[str, bool], ...] = (
    ("lexical", False),
    ("lexical_idf", False),
    ("dense", True),
    ("hybrid_rrf", True),
    ("hybrid_rrf_idf", True),
)
DEFAULT_CHUNKERS: tuple[str, ...] = ("hierarchical", "fixed")
PREFERRED_EMBEDDER = "bge_m3"
FALLBACK_EMBEDDER = "fake"
RUN_CSV = "eval_{stamp}.csv"
PER_QUERY_CSV = "eval_{stamp}_per_query.csv"
LATEST_JSON = "eval_latest.json"

Warn = Callable[[str], None]


class EvalConfigSpec(EvalConfig):
    """EvalConfig plus what the graph side and the prerequisite check need."""

    inner_searcher: str | None = Field(
        default=None, description="seed searcher when the searcher is the graph walker"
    )
    hops: int | None = Field(default=None, description="graph_hops override for this run")
    needs_embeddings: bool = True
    needs_graph: bool = False
    filter_course: bool = Field(
        default=False, description="retrieval was restricted to the course tag of the query"
    )

    @property
    def base_searcher(self) -> str:
        """The searcher being compared: the walker's inner searcher on the graph side."""
        return self.inner_searcher or self.searcher

    @property
    def label(self) -> str:
        return f"{self.rag}/{self.base_searcher}/{self.chunker}/{self.embedder}"


class Prerequisites(BaseModel):
    """What the database currently holds, used to skip impossible configurations."""

    chunks: dict[str, int] = Field(default_factory=dict)
    vectors: dict[str, int] = Field(default_factory=dict, description="'<embedder>/<strategy>'")
    graph_chunks: dict[str, int] = Field(default_factory=dict, description="per strategy")

    def missing(self, spec: EvalConfigSpec) -> str | None:
        if not self.chunks.get(spec.chunker):
            return f"no chunks for strategy {spec.chunker}"
        space = vector_space(spec.embedder)
        if spec.needs_embeddings and not self.vectors.get(f"{space}/{spec.chunker}"):
            return f"no {space} embeddings for strategy {spec.chunker}"
        if spec.needs_graph and not self.graph_chunks.get(spec.chunker):
            return f"graph holds no {spec.chunker} chunks"
        return None


def vector_space(embedder: str) -> str:
    """Embedder column under which the vectors of this embedder are stored (bge_m3_hf -> bge_m3)."""
    try:
        space: str | None = getattr(registry.get("embedder", embedder), "space", None)
    except Exception:
        return embedder
    return space or embedder


def default_matrix(
    k: int,
    chunkers: list[str] | None = None,
    embedders: list[str] | None = None,
    rags: list[str] | None = None,
    searchers: list[str] | None = None,
    hops: int | None = None,
) -> list[EvalConfigSpec]:
    """Expand the recipes into one configuration per (rag, searcher, chunker, embedder)."""
    wanted_rags = set(rags or [name for name, _ in RAG_RECIPES])
    wanted_searchers = set(searchers or [name for name, _ in SEARCHER_RECIPES])
    configs: list[EvalConfigSpec] = []
    for rag_name, wrapper in RAG_RECIPES:
        if rag_name not in wanted_rags:
            continue
        for base, needs_embeddings in SEARCHER_RECIPES:
            if base not in wanted_searchers:
                continue
            for chunker in chunkers or list(DEFAULT_CHUNKERS):
                for embedder in embedders or [PREFERRED_EMBEDDER]:
                    configs.append(
                        EvalConfigSpec(
                            rag=rag_name,
                            chunker=chunker,
                            searcher=wrapper or base,
                            inner_searcher=base if wrapper else None,
                            embedder=embedder,
                            k=k,
                            hops=hops if wrapper else None,
                            needs_embeddings=needs_embeddings,
                            needs_graph=wrapper is not None,
                        )
                    )
    return configs


def read_support(settings: Settings) -> dict[str, str]:
    """Map document id to its metadata support label (primary corpus vs background reading)."""
    store = PostgresStore(settings)
    with store.connection() as conn:
        rows = conn.execute("SELECT id, metadata->>'support' AS support FROM documents").fetchall()
    return {row["id"]: row["support"] for row in rows if row["support"]}


def read_prerequisites(settings: Settings) -> Prerequisites:
    """Count chunks, vectors and graph attachments once so every config can be checked cheaply."""
    store = PostgresStore(settings)
    prerequisites = Prerequisites()
    with store.connection() as conn:
        for row in conn.execute("SELECT strategy, count(*) AS n FROM chunks GROUP BY strategy"):
            prerequisites.chunks[row["strategy"]] = int(row["n"])
        for row in conn.execute(
            """
            SELECT e.embedder AS embedder, c.strategy AS strategy, count(*) AS n
            FROM embeddings e JOIN chunks c ON c.id = e.chunk_id
            GROUP BY e.embedder, c.strategy
            """
        ):
            prerequisites.vectors[f"{row['embedder']}/{row['strategy']}"] = int(row["n"])
        for row in conn.execute(
            "SELECT split_part(chunk_id, ':', 1) AS strategy, count(*) AS n"
            " FROM node_chunks GROUP BY 1"
        ):
            prerequisites.graph_chunks[row["strategy"]] = int(row["n"])
    return prerequisites


def resolve(
    spec: EvalConfigSpec, prerequisites: Prerequisites, warn: Warn
) -> EvalConfigSpec | None:
    """Keep the config, downgrade its embedder to the offline one, or skip it with a reason."""
    reason = prerequisites.missing(spec)
    if reason is None:
        return spec
    downgraded = spec.model_copy(update={"embedder": FALLBACK_EMBEDDER})
    if spec.needs_embeddings and prerequisites.missing(downgraded) is None:
        warn(f"{spec.label}: {reason} -> FALLING BACK to the {FALLBACK_EMBEDDER} embedder")
        return downgraded
    warn(f"{spec.label}: skipped ({reason})")
    return None


def build_rag(settings: Settings, spec: EvalConfigSpec) -> tuple[RAG, PostgresStore]:
    """Create store, embedder, searcher and rag of one configuration through the registry."""
    store = GraphStore(settings)
    embedder = registry.create("embedder", spec.embedder, settings=settings)
    searcher_kwargs: dict[str, Any] = {"store": store, "embedder": embedder, "settings": settings}
    if spec.inner_searcher is not None:
        searcher_kwargs["inner_name"] = spec.inner_searcher
    searcher = registry.create("searcher", spec.searcher, **searcher_kwargs)
    rag: RAG = registry.create("rag", spec.rag, searcher=searcher, store=store, settings=settings)
    return rag, store


def settings_for(settings: Settings, spec: EvalConfigSpec) -> Settings:
    """Per-configuration settings: the embedder and the graph depth belong to the strategy."""
    update: dict[str, Any] = {"embedding_provider": spec.embedder, "chunker": spec.chunker}
    if spec.hops is not None:
        update["graph_hops"] = spec.hops
    return settings.model_copy(update=update)


def top_k(context: RetrievedContext, k: int) -> list[ScoredChunk]:
    """Both rags append extra chunks beyond k; rank everything by score and keep k."""
    return sorted(context.chunks, key=lambda sc: -sc.score)[:k]


def run_config(
    rag: RAG,
    spec: EvalConfigSpec,
    queries: list[EvalQueryFile],
    k: int,
    filter_course: bool = False,
    support: dict[str, str] | None = None,
) -> tuple[list[QueryMetrics], str | None]:
    """Run every query on one prepared rag instance and time each retrieval separately."""
    results: list[QueryMetrics] = []
    inner: str | None = None
    for query in queries:
        # the course filter is opt-in: without it a query may be confused by the other course
        course = query.tag_value("course") if filter_course else None
        filters = SearchFilters(strategy=spec.chunker, course=course)
        started = perf_counter()
        context = rag.retrieve(query.query, k, filters)
        latency_ms = (perf_counter() - started) * 1000.0
        inner = context.trace.get("inner_searcher") or inner
        results.append(query_metrics(top_k(context, k), query, k, latency_ms, support))
    return results, inner


def run_matrix(
    settings: Settings,
    configs: list[EvalConfig],
    queries: list[EvalQueryFile],
    k: int,
    out_dir: Path,
    warn: Warn = print,
    filter_course: bool = False,
) -> list[EvalRun]:
    """Run every configuration over the gold set and write csv, json and database rows."""
    prerequisites = read_prerequisites(settings)
    support = read_support(settings)
    runs: list[EvalRun] = []
    per_query_rows: list[dict[str, Any]] = []
    for config in configs:
        spec = (
            config if isinstance(config, EvalConfigSpec) else EvalConfigSpec(**config.model_dump())
        )
        resolved = resolve(spec, prerequisites, warn)
        if resolved is None:
            continue
        # record what the run actually did so the stored config never hides it
        update: dict[str, Any] = {"filter_course": filter_course}
        if resolved.needs_graph and resolved.hops is None:
            update["hops"] = settings.graph_hops
        resolved = resolved.model_copy(update=update)
        run_settings = settings_for(settings, resolved)
        try:
            rag, _ = build_rag(run_settings, resolved)
        except Exception as exc:  # noqa: BLE001 - a broken config must not stop the matrix
            warn(f"{resolved.label}: skipped (cannot build: {exc})")
            continue
        results, inner = run_config(rag, resolved, queries, k, filter_course, support)
        if inner is not None:
            resolved = resolved.model_copy(update={"inner_searcher": inner})
        metrics = aggregate(results)
        runs.append(EvalRun(config=resolved, metrics=metrics))
        per_query_rows.extend(_per_query_rows(resolved, results))
    _write_outputs(settings, runs, per_query_rows, out_dir)
    return runs


def _per_query_rows(spec: EvalConfigSpec, results: list[QueryMetrics]) -> list[dict[str, Any]]:
    return [
        {
            "config": spec.label,
            "rag": spec.rag,
            "searcher": spec.base_searcher,
            "chunker": spec.chunker,
            "embedder": spec.embedder,
            "hops": spec.hops if spec.hops is not None else "",
            "k": spec.k,
            "query_id": result.query_id,
            "hit": result.hit,
            "first_relevant_rank": (
                result.first_relevant_rank if result.first_relevant_rank is not None else ""
            ),
            "recall_at_k": round(result.recall_at_k, 4),
            "section_recall_at_k": (
                round(result.section_recall_at_k, 4)
                if result.section_recall_at_k is not None
                else ""
            ),
            "mrr": round(result.mrr, 4),
            "ndcg_at_k": round(result.ndcg_at_k, 4),
            "n_chunks": result.context.n_chunks,
            "n_background": result.context.support.get("background", 0),
            "context_chars": result.context.total_chars,
            "latency_ms": round(result.latency_ms, 2),
        }
        for result in results
    ]


def _run_row(run: EvalRun) -> dict[str, Any]:
    spec = run.config
    metrics = run.metrics
    row: dict[str, Any] = {
        "config": spec.label if isinstance(spec, EvalConfigSpec) else "",
        "rag": spec.rag,
        "searcher": spec.base_searcher if isinstance(spec, EvalConfigSpec) else spec.searcher,
        "chunker": spec.chunker,
        "embedder": spec.embedder,
        "hops": getattr(spec, "hops", None) or "",
        "k": spec.k,
        "filter_course": getattr(spec, "filter_course", False),
    }
    dumped = metrics.model_dump()
    distributions = {
        name: dumped.pop(name, {}) for name in ("kind_distribution", "support_distribution")
    }
    row.update(
        {
            key: round(value, 4) if isinstance(value, float) else value
            for key, value in dumped.items()
        }
    )
    for name, shares in distributions.items():
        row[name] = ";".join(f"{key}={share:.2f}" for key, share in shares.items())
    return row


def _write_outputs(
    settings: Settings, runs: list[EvalRun], per_query_rows: list[dict[str, Any]], out_dir: Path
) -> None:
    """Write the two csv files and the json snapshot, then insert one eval_runs row per config."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_rows = [_run_row(run) for run in runs]
    write_csv(out_dir / RUN_CSV.format(stamp=stamp), run_rows)
    write_csv(out_dir / PER_QUERY_CSV.format(stamp=stamp), per_query_rows)
    (out_dir / LATEST_JSON).write_text(
        json.dumps([run_payload(run) for run in runs], indent=2, default=str), encoding="utf-8"
    )
    try:
        insert_runs(settings, runs)
    except Exception as exc:  # noqa: BLE001 - losing the db row must not lose the csv
        print(f"eval_runs insert failed: {exc}")


def run_payload(run: EvalRun) -> dict[str, Any]:
    """Serialize a run without losing the extra fields of the config and metrics subclasses."""
    return {
        "config": run.config.model_dump(),
        "metrics": run.metrics.model_dump(),
        "created_at": run.created_at.isoformat(),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write rows as csv with the keys of the first row as the header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not rows:
            handle.write("")
            return path
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def insert_runs(settings: Settings, runs: list[EvalRun]) -> int:
    """Store every run as one eval_runs row with the config and metrics json."""
    if not runs:
        return 0
    store = PostgresStore(settings)
    with store.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO eval_runs (config, metrics) VALUES (%s, %s)",
            [
                (json.dumps(run.config.model_dump()), json.dumps(run.metrics.model_dump()))
                for run in runs
            ],
        )
        conn.commit()
    return len(runs)


def build_configs(
    k: int,
    chunkers: list[str] | None = None,
    embedders: list[str] | None = None,
    rags: list[str] | None = None,
    searchers: list[str] | None = None,
    hops_values: list[int] | None = None,
) -> list[EvalConfigSpec]:
    """Default matrix, or one matrix per requested hop count with the duplicates removed."""
    if not hops_values:
        return default_matrix(k, chunkers, embedders, rags, searchers)
    configs: list[EvalConfigSpec] = []
    seen: set[tuple[str, int | None]] = set()
    for hops in hops_values:
        for spec in default_matrix(k, chunkers, embedders, rags, searchers, hops=hops):
            key = (spec.label, spec.hops)
            if key in seen:
                continue
            seen.add(key)
            configs.append(spec)
    return configs


def spec_from_label(label: str, k: int, hops: int | None = None) -> EvalConfigSpec:
    """Parse 'rag/searcher/chunker/embedder' into one configuration using the recipe tables."""
    parts = label.split("/")
    if len(parts) != 4:
        raise ValueError(f"expected rag/searcher/chunker/embedder, got {label!r}")
    rag_name, base, chunker, embedder = parts
    wrappers = dict(RAG_RECIPES)
    if rag_name not in wrappers:
        raise ValueError(f"unknown rag {rag_name!r}; known: {sorted(wrappers)}")
    needs = dict(SEARCHER_RECIPES)
    if base not in needs:
        raise ValueError(f"unknown searcher {base!r}; known: {sorted(needs)}")
    wrapper = wrappers[rag_name]
    return EvalConfigSpec(
        rag=rag_name,
        chunker=chunker,
        searcher=wrapper or base,
        inner_searcher=base if wrapper else None,
        embedder=embedder,
        k=k,
        hops=hops if wrapper else None,
        needs_embeddings=needs[base],
        needs_graph=wrapper is not None,
    )
