"""
Role:   Typer sub-app with the evaluation commands; merged into the root CLI.
Input:  CLI options, eval/queries.yaml, the corpus in Postgres and a markdown file for the judge.
Output: rich tables on the console; results/*.csv, results/eval_latest.json, eval_runs rows.
Flow:   `eval` builds the requested configurations and hands them to run_matrix, then prints the
        runs sorted by nDCG; `eval-queries` loads the gold set, validates every expected id
        against the corpus and prints the counts per tag; `judge` scores one generated lab.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rag_lab_generator.config import get_settings
from rag_lab_generator.eval import runner
from rag_lab_generator.eval.judge import judge_lab
from rag_lab_generator.eval.queries import (
    QUERIES_PATH,
    EvalQueryFile,
    corpus_index,
    filter_by_tag,
    load_queries,
    validate_queries,
)
from rag_lab_generator.models import EvalRun

app = typer.Typer(help="Retrieval evaluation")
console = Console()
SETTINGS = get_settings()
WIDE_CONSOLE = 150
COMPACT_COLUMNS: frozenset[str] = frozenset(
    {"hit_at_k", "recall_at_k", "mrr", "ndcg_at_k", "latency_ms_p50"}
)
RUN_COLUMNS: tuple[tuple[str, str], ...] = (
    ("hit_at_k", "hit@k"),
    ("recall_at_k", "recall@k"),
    ("section_recall_at_k", "sect@k"),
    ("coverage", "cover"),
    ("mrr", "MRR"),
    ("ndcg_at_k", "nDCG@k"),
    ("latency_ms_p50", "p50 ms"),
    ("latency_ms_p50_warm", "warm ms"),
    ("context_chars_mean", "chars"),
)


@app.command("eval")
def evaluate(
    matrix: bool = typer.Option(False, "--matrix", help="run every strategy combination"),
    config: str | None = typer.Option(
        None, "--config", help="single run: rag/searcher/chunker/embedder"
    ),
    k: int = typer.Option(SETTINGS.retrieval_k, "-k", "--k", help="context size"),
    chunker: list[str] | None = typer.Option(None, help="restrict to these chunkers"),
    embedder: list[str] | None = typer.Option(None, help="restrict to these embedders"),
    rag: list[str] | None = typer.Option(None, help="restrict to these rag strategies"),
    searcher: list[str] | None = typer.Option(None, help="restrict to these searchers"),
    hops: list[int] | None = typer.Option(None, help="graph hop counts to sweep"),
    tag: list[str] | None = typer.Option(None, help="keep only queries carrying every tag"),
    queries: Path = typer.Option(QUERIES_PATH, help="gold query file"),
    out_dir: Path = typer.Option(SETTINGS.results_dir, help="where the csv and json are written"),
    course_filter: bool = typer.Option(
        False, help="restrict retrieval to the course of the query tag"
    ),
) -> None:
    """Evaluate retrieval quality against the gold query set."""
    gold = filter_by_tag(load_queries(queries), list(tag) if tag else [])
    if not gold:
        console.print("[red]no queries selected[/red]")
        raise typer.Exit(code=1)
    if config is not None:
        try:
            configs = [runner.spec_from_label(config, k, hops[0] if hops else None)]
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
    elif matrix:
        configs = runner.build_configs(
            k,
            list(chunker) if chunker else None,
            list(embedder) if embedder else None,
            list(rag) if rag else None,
            list(searcher) if searcher else None,
            list(hops) if hops else None,
        )
    else:
        console.print("[red]pass --matrix or --config rag/searcher/chunker/embedder[/red]")
        raise typer.Exit(code=1)
    console.print(f"{len(configs)} configurations x {len(gold)} queries, k={k}")
    runs = runner.run_matrix(
        SETTINGS,
        list(configs),
        gold,
        k,
        out_dir,
        warn=lambda m: console.print(f"[yellow]{m}[/]"),
        filter_course=course_filter,
    )
    if not runs:
        console.print("[red]every configuration was skipped[/red]")
        raise typer.Exit(code=1)
    _print_runs(runs)
    console.print(f"wrote {out_dir}/eval_latest.json and the csv files next to it")


@app.command("eval-queries")
def eval_queries(
    queries: Path = typer.Option(QUERIES_PATH, help="gold query file"),
    tag: list[str] | None = typer.Option(None, help="keep only queries carrying every tag"),
    show: bool = typer.Option(False, help="print every query with its expectations"),
) -> None:
    """List the gold set and check that every expected lab, document and section id exists."""
    gold = filter_by_tag(load_queries(queries), list(tag) if tag else [])
    index = corpus_index(SETTINGS)
    issues = validate_queries(gold, index)
    if show:
        _print_queries(gold)
    _print_tag_counts(gold)
    console.print(
        f"{len(gold)} queries validated against {len(index.document_ids)} documents "
        f"({index.source})"
    )
    if issues:
        table = Table(title="unknown ids")
        for column in ("query", "field", "value"):
            table.add_column(column, overflow="fold")
        for issue in issues:
            table.add_row(issue.query_id, issue.field, issue.value)
        console.print(table)
        raise typer.Exit(code=1)
    console.print("[green]every expected id exists[/green]")


@app.command("judge")
def judge(
    file: Path = typer.Argument(..., help="markdown file holding the generated lab"),
    lab: list[str] | None = typer.Option(None, help="reference lab ids, e.g. sop1/l3"),
    llm: str | None = typer.Option(None, help="llm name; defaults to the configured provider"),
    show_prompt: bool = typer.Option(False, help="print the prompt sent to the judge"),
) -> None:
    """Score a generated lab 1-5 on style, difficulty, api grounding and completeness."""
    result = judge_lab(SETTINGS, file.read_text(encoding="utf-8"), list(lab) if lab else None, llm)
    table = Table(title=f"judge: {file.name} ({result.model})")
    table.add_column("criterion")
    table.add_column("score", justify="right")
    for name, value in result.scores.model_dump().items():
        table.add_row(name, str(value))
    table.add_row("overall", f"{result.scores.overall:.2f}")
    console.print(table)
    if not result.parsed:
        console.print(
            "[yellow]placeholder scores: the provider returned no json "
            "(real scores need ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic)[/yellow]"
        )
    if show_prompt:
        console.rule("prompt")
        console.print(result.prompt)


def _print_runs(runs: list[EvalRun]) -> None:
    """Render one row per configuration, best nDCG first."""
    # a narrow console gets the five headline metrics; the csv always holds every column
    columns = [c for c in RUN_COLUMNS if console.width >= WIDE_CONSOLE or c[0] in COMPACT_COLUMNS]
    table = Table(title="retrieval evaluation")
    for column in ("rag", "searcher", "chunker", "embedder", "hops"):
        table.add_column(column)
    for _, header in columns:
        table.add_column(header, justify="right")
    for run in sorted(runs, key=lambda r: -r.metrics.ndcg_at_k):
        values = run.metrics.model_dump()
        table.add_row(
            run.config.rag,
            getattr(run.config, "base_searcher", run.config.searcher),
            run.config.chunker,
            run.config.embedder,
            str(getattr(run.config, "hops", None) or "-"),
            *(f"{values.get(key, 0.0):.3f}" for key, _ in columns),
        )
    console.print(table)


def _print_queries(gold: list[EvalQueryFile]) -> None:
    table = Table(title="gold queries")
    for column in ("id", "query", "labs", "documents", "sections", "tags"):
        table.add_column(column, overflow="fold")
    for query in gold:
        table.add_row(
            query.id,
            query.query,
            ", ".join(query.expected_lab_ids),
            ", ".join(query.expected_document_ids),
            ", ".join(query.expected_section_ids),
            ", ".join(query.tags),
        )
    console.print(table)


def _print_tag_counts(gold: list[EvalQueryFile]) -> None:
    counts: dict[str, int] = {}
    for query in gold:
        for item in query.tags:
            counts[item] = counts.get(item, 0) + 1
        for lab_id in query.expected_lab_ids:
            counts[f"lab:{lab_id}"] = counts.get(f"lab:{lab_id}", 0) + 1
    table = Table(title="gold set composition")
    table.add_column("tag")
    table.add_column("queries", justify="right")
    for key, value in sorted(counts.items()):
        table.add_row(key, str(value))
    console.print(table)
