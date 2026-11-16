"""
Role:   Typer sub-app with the ingestion commands (ingest, summarize, corpus-stats).
Input:  CLI options: courses, force, skip-summaries, lab selector.
Output: Populated data/raw tree and rich tables on the console.
Flow:   Each command reads Settings, calls the matching pipeline entry point and renders the
        result as a rich table; corpus-stats reads data/raw back through load_documents().
"""

from collections import defaultdict

import typer
from rich.console import Console
from rich.table import Table

from rag_lab_generator.config import get_settings
from rag_lab_generator.ingestion.pipeline import (
    IngestReport,
    load_documents,
    regenerate_summaries,
    run_ingest,
    run_ingest_without_summaries,
)

app = typer.Typer(help="Corpus ingestion")
console = Console()

DEFAULT_COURSES = ["sop1", "sop2"]


def _report_table(report: IngestReport) -> Table:
    table = Table(title="ingestion report")
    for column in (
        "course",
        "labs",
        "sections",
        "tasks",
        "code",
        "lectures",
        "pdfs",
        "info",
        "extra",
    ):
        table.add_column(column, justify="right" if column != "course" else "left")
    for course, counts in sorted(report.courses.items()):
        table.add_row(
            course,
            str(counts.labs),
            str(counts.sections),
            str(counts.tasks),
            str(counts.code_files),
            str(counts.lectures),
            str(counts.lecture_pdfs),
            str(counts.course_pages),
            str(counts.external_files),
        )
    return table


@app.command()
def ingest(
    course: list[str] = typer.Option(DEFAULT_COURSES, help="courses to ingest"),
    force: bool = typer.Option(False, help="re-clone and re-download every source"),
    skip_summaries: bool = typer.Option(False, help="do not call the llm for summary.md"),
) -> None:
    """Fetch every source and build data/raw/<course>/<lab>/."""
    settings = get_settings()
    if skip_summaries:
        report = run_ingest_without_summaries(settings, list(course), force)
    else:
        report = run_ingest(settings, list(course), force)
    console.print(_report_table(report))
    console.print(f"summaries: {report.summaries}  raw_dir: {report.raw_dir}")
    if report.skipped:
        console.print(
            f"[yellow]skipped {len(report.skipped)} files[/yellow]: {report.skipped[:10]}"
        )


@app.command()
def summarize(
    course: list[str] = typer.Option(DEFAULT_COURSES, help="courses to summarize"),
    lab: str | None = typer.Option(None, help="single lab id or slug, e.g. sop1/l1"),
) -> None:
    """Regenerate summary.md and summary.pdf with the configured llm provider."""
    settings = get_settings()
    written = regenerate_summaries(settings, list(course), lab)
    console.print(f"rewrote {len(written)} summaries with llm '{settings.llm_provider}'")
    for lab_id in written:
        console.print(f"  {lab_id}")


@app.command(name="corpus-stats")
def corpus_stats(
    course: list[str] = typer.Option(DEFAULT_COURSES, help="courses to inspect"),
) -> None:
    """Print how many documents, sections and characters data/raw holds, by kind and course."""
    documents = load_documents(get_settings(), list(course))
    buckets: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for document in documents:
        bucket = buckets[(document.course.value, document.kind.value)]
        bucket[0] += 1
        bucket[1] += len(document.sections)
        bucket[2] += len(document.text)

    table = Table(title="corpus statistics")
    table.add_column("course")
    table.add_column("kind")
    table.add_column("documents", justify="right")
    table.add_column("sections", justify="right")
    table.add_column("chars", justify="right")
    for (course_name, kind), (count, sections, chars) in sorted(buckets.items()):
        table.add_row(course_name, kind, str(count), str(sections), f"{chars:,}")
    totals = [sum(value[index] for value in buckets.values()) for index in range(3)]
    table.add_section()
    table.add_row("all", "all", str(totals[0]), str(totals[1]), f"{totals[2]:,}")
    console.print(table)
