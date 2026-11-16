"""
Role:   Typer sub-app with retrieval commands (chunk, index, query, db-init, db-stats).
Input:  CLI options; documents from the ingestion pipeline; rows already in Postgres.
Output: Chunk, embedding rows in Postgres; rich tables on the console.
Flow:   Every command builds its components through the registry with Settings defaults, talks to
        VectorStore and prints a short report; `chunk` imports the ingestion pipeline lazily so
        the retrieval CLI stays usable while ingestion is still being written.
"""

from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from rag_lab_generator import registry
from rag_lab_generator.config import get_settings
from rag_lab_generator.models import Chunk, RetrievedContext
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.stores.vector_store import VectorStore

app = typer.Typer(help="Chunking, indexing, querying")
console = Console()
SETTINGS = get_settings()
PREVIEW_CHARS = 120


@app.command()
def chunk(
    strategy: str = typer.Option(SETTINGS.chunker, help="chunker name"),
    course: list[str] | None = typer.Option(None, help="restrict to these courses"),
    replace: bool = typer.Option(False, help="delete existing chunks of this strategy first"),
    embedder: str = typer.Option(
        SETTINGS.embedding_provider, help="embedder used by the semantic splitter"
    ),
) -> None:
    """Load documents, chunk them with one strategy and store documents and chunks."""
    from rag_lab_generator.ingestion.pipeline import load_documents

    settings = SETTINGS.model_copy(update={"embedding_provider": embedder})
    store = VectorStore(settings)
    docs = load_documents(settings, list(course) if course else None)
    if not docs:
        console.print("[yellow]no documents found[/yellow]")
        raise typer.Exit(code=1)
    store.upsert_documents(docs)
    if replace:
        console.print(f"deleted {store.delete_chunks(strategy)} existing chunks")
    chunker = registry.create("chunker", strategy, settings=settings)
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunker.chunk(doc))
    store.upsert_chunks(chunks)
    console.print(
        f"[green]{strategy}[/green]: {len(docs)} documents -> {len(chunks)} chunks "
        f"(avg {sum(c.char_count for c in chunks) // max(len(chunks), 1)} chars)"
    )


@app.command()
def index(
    embedder: str = typer.Option(SETTINGS.embedding_provider, help="embedder name"),
    strategy: str = typer.Option(SETTINGS.chunker, help="chunker name whose chunks are embedded"),
    replace: bool = typer.Option(False, help="drop existing vectors of this embedder first"),
) -> None:
    """Embed every chunk of one strategy that has no vector for this embedder yet."""
    store = VectorStore(SETTINGS)
    model = registry.create("embedder", embedder, settings=SETTINGS)
    # Vectors are stored under the embedder's vector space, so bge_m3_hf fills the bge_m3 rows.
    space = model.vector_space
    if replace:
        console.print(f"deleted {store.delete_embeddings(space)} existing vectors")
    pending = store.chunks_without_embeddings(space, strategy)
    if not pending:
        console.print(f"[green]nothing to do[/green]: {embedder}/{strategy} is up to date")
        return
    batch_size = SETTINGS.embedding_batch_size
    with Progress(console=console) as progress:
        task = progress.add_task(f"embedding {len(pending)} chunks", total=len(pending))
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            vectors = model.embed_documents([c.text for c in batch])
            store.upsert_embeddings(space, [c.id for c in batch], vectors)
            progress.advance(task, len(batch))
    console.print(f"[green]{embedder}[/green]: indexed {len(pending)} chunks of {strategy}")


@app.command()
def query(
    text: str = typer.Argument(..., help="natural language query"),
    rag: str = typer.Option(SETTINGS.rag, help="rag strategy"),
    searcher: str = typer.Option(SETTINGS.searcher, help="searcher name"),
    strategy: str = typer.Option(SETTINGS.chunker, help="chunker name to search in"),
    embedder: str = typer.Option(SETTINGS.embedding_provider, help="embedder name"),
    k: int = typer.Option(SETTINGS.retrieval_k, "-k", "--k", help="number of chunks"),
    course: str | None = typer.Option(None, help="filter by course"),
    lab: str | None = typer.Option(None, help="filter by lab id"),
    kind: list[str] | None = typer.Option(None, help="filter by chunk kind"),
    show_text: bool = typer.Option(False, help="print the full text of every chunk"),
) -> None:
    """Retrieve context for a query with the configured RAG strategy."""
    store = VectorStore(SETTINGS)
    model = registry.create("embedder", embedder, settings=SETTINGS)
    searcher_impl = registry.create(
        "searcher", searcher, store=store, embedder=model, settings=SETTINGS
    )
    rag_impl = registry.create("rag", rag, searcher=searcher_impl, store=store, settings=SETTINGS)
    filters = SearchFilters(
        strategy=strategy, course=course, lab_id=lab, kinds=list(kind) if kind else None
    )
    context: RetrievedContext = rag_impl.retrieve(text, k, filters)
    _print_context(context, show_text=show_text)


@app.command("db-init")
def db_init() -> None:
    """Apply sql/001_schema.sql to the configured database."""
    VectorStore(SETTINGS).apply_schema()
    console.print(f"[green]schema applied[/green] on {SETTINGS.database_url}")


@app.command("db-stats")
def db_stats() -> None:
    """Print row counts per table, per chunking strategy and per embedder."""
    store = VectorStore(SETTINGS)
    _print_counts("tables", "table", store.count_rows())
    _print_counts("chunks", "strategy", store.count_chunks_by_strategy())
    _print_counts("embeddings", "embedder", store.count_embeddings_by_embedder())


def _print_counts(title: str, column: str, counts: list[tuple[str, int]]) -> None:
    table = Table(title=title)
    table.add_column(column)
    table.add_column("rows", justify="right")
    for key, value in counts:
        table.add_row(key, str(value))
    console.print(table)


def _print_context(context: RetrievedContext, show_text: bool) -> None:
    """Render the retrieved chunks as a table and the trace as a footer line."""
    table = Table(title=f"{context.rag} / {context.query}")
    for column in ("score", "chunk id", "kind", "section", "preview"):
        table.add_column(column, overflow="fold")
    for scored in context.chunks:
        chunk = scored.chunk
        preview = " ".join(chunk.text.split())[:PREVIEW_CHARS]
        table.add_row(
            f"{scored.score:.4f}",
            chunk.id,
            chunk.kind.value,
            chunk.section_id or "-",
            preview,
        )
    console.print(table)
    console.print(_format_trace(context.trace))
    if show_text:
        for scored in context.chunks:
            console.rule(f"{scored.chunk.id}  ({scored.source})")
            console.print(scored.chunk.text)


def _format_trace(trace: dict[str, Any]) -> str:
    return "trace: " + "  ".join(f"{key}={value}" for key, value in trace.items())
