"""
Role:   Typer sub-app with the knowledge-graph commands, merged into the root `rag-lab` CLI.
Input:  CLI options; Postgres rows written by ingestion and chunking.
Output: Graph rows in Postgres, console tables, exported graphml/dot files.
Flow:   graph-build rebuilds the graph, graph-describe generates the node descriptions with the
        configured llm, graph-stats prints the counts, graph-neighbors walks a node's
        neighbourhood, graph-export writes the graph for Gephi/Graphviz and graph-query runs the
        graph RAG and prints the retrieved chunks together with their node paths.
"""

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Knowledge graph build, inspection and graph RAG queries")
console = Console()


@app.command("graph-build")
def graph_build(
    strategy: str = typer.Option("hierarchical", "--strategy", help="chunker whose chunks to link"),
    course: list[str] | None = typer.Option(None, "--course", help="restrict to these courses"),
) -> None:
    """Rebuild the knowledge graph from the ingested documents and the chunks of one strategy."""
    from rag_lab_generator.config import get_settings
    from rag_lab_generator.retrieval.graph.builder import build_graph

    stats = build_graph(get_settings(), strategy, list(course) if course else None)
    _print_counts("graph build", stats)


@app.command("graph-describe")
def graph_describe(
    kind: list[str] | None = typer.Option(
        None, "--kind", help="node kinds to describe; default concept, api_function, lecture"
    ),
    force: bool = typer.Option(
        False, "--force", help="regenerate even when the sources are unchanged"
    ),
    limit: int = typer.Option(0, "--limit", help="stop after this many nodes; 0 means all"),
    llm: str = typer.Option("", "--llm", help="llm provider name; default from settings"),
) -> None:
    """Generate the short description shown for concept, api and lecture nodes."""
    from rich.progress import Progress

    from rag_lab_generator import registry
    from rag_lab_generator.config import get_settings
    from rag_lab_generator.models import NodeKind
    from rag_lab_generator.retrieval.graph.describer import describe_nodes
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore

    settings = get_settings()
    model = registry.create("llm", llm or settings.llm_provider, settings=settings)
    kinds = [NodeKind(name) for name in kind] if kind else None
    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("describing nodes", total=None)
        report = describe_nodes(
            GraphStore(settings),
            model,
            kinds,
            force=force,
            limit=limit or None,
            progress=lambda node: progress.update(task, advance=1, description=node.id[:60]),
        )
    _print_counts("graph describe", report.model_dump(exclude={"model"}))
    console.print(f"model: {report.model}")


@app.command("graph-stats")
def graph_stats() -> None:
    """Print how many nodes and edges of each kind the stored graph has."""
    from rag_lab_generator.config import get_settings
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore

    _print_counts("graph stats", GraphStore(get_settings()).stats())


@app.command("graph-neighbors")
def graph_neighbors(
    node_id: str = typer.Argument(..., help="node id, e.g. api:opendir or sop1/l1"),
    hops: int = typer.Option(1, "--hops", help="neighbourhood radius"),
) -> None:
    """Show the neighbourhood of one node up to the given number of hops."""
    from rag_lab_generator.config import get_settings
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore

    graph = GraphStore(get_settings()).load_graph()
    if not graph.has_node(node_id):
        raise typer.BadParameter(f"unknown node {node_id!r}")
    table = Table(title=f"{node_id} ({graph.nodes[node_id].get('kind')})")
    for column in ("hop", "direction", "kind", "node", "label"):
        table.add_column(column)
    frontier = {node_id}
    seen = {node_id}
    for hop in range(1, max(1, hops) + 1):
        following: set[str] = set()
        for current in sorted(frontier):
            for neighbour, kind, direction in _incident(graph, current):
                if neighbour in seen:
                    continue
                seen.add(neighbour)
                following.add(neighbour)
                data = graph.nodes[neighbour]
                table.add_row(str(hop), direction, kind, neighbour, str(data.get("label", ""))[:60])
        frontier = following
    console.print(table)


@app.command("graph-export")
def graph_export(
    fmt: str = typer.Option("graphml", "--format", help="graphml or dot"),
    out: Path = typer.Option(Path("results/graph.graphml"), "--out", help="output file"),
) -> None:
    """Export the stored graph for Gephi (graphml) or Graphviz (dot)."""
    import networkx as nx

    from rag_lab_generator.config import get_settings
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore

    graph = GraphStore(get_settings()).load_graph()
    flat = _flatten(graph)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "graphml":
        nx.write_graphml(flat, out)
    elif fmt == "dot":
        out.write_text(_to_dot(flat), encoding="utf-8")
    else:
        raise typer.BadParameter("format must be graphml or dot")
    console.print(f"wrote {flat.number_of_nodes()} nodes / {flat.number_of_edges()} edges to {out}")


@app.command("graph-query")
def graph_query(
    text: str = typer.Argument(..., help="natural language query"),
    k: int = typer.Option(0, "--k", help="number of chunks; 0 uses settings.retrieval_k"),
    strategy: str = typer.Option("hierarchical", "--strategy", help="chunking strategy filter"),
    embedder: str = typer.Option("", "--embedder", help="embedder name; default from settings"),
    inner: str = typer.Option("", "--inner", help="inner seeding searcher for the graph walk"),
    course: str = typer.Option("", "--course", help="restrict to one course"),
    lab: str = typer.Option("", "--lab", help="restrict to one lab id"),
) -> None:
    """Run the graph RAG for one query and print the chunks with the node path that found them."""
    from rag_lab_generator import registry
    from rag_lab_generator.config import get_settings
    from rag_lab_generator.retrieval.rag.base import RAG
    from rag_lab_generator.retrieval.searchers.base import SearchFilters
    from rag_lab_generator.retrieval.stores.graph_store import GraphStore

    settings = get_settings()
    store = GraphStore(settings)
    embedder_impl = registry.create(
        "embedder", embedder or settings.embedding_provider, settings=settings
    )
    searcher = registry.create(
        "searcher",
        "graph_walk",
        store=store,
        embedder=embedder_impl,
        settings=settings,
        inner_name=inner or None,
    )
    rag: RAG = registry.create("rag", "graph", searcher=searcher, store=store, settings=settings)
    filters = SearchFilters(
        strategy=strategy, course=course or None, lab_id=lab or None, kinds=None
    )
    context = rag.retrieve(text, k or settings.retrieval_k, filters)
    table = Table(title=f"graph rag: {text}")
    for column in ("score", "chunk", "kind", "source", "path"):
        table.add_column(column, overflow="fold")
    for scored in context.chunks:
        path = scored.chunk.metadata.get("path", [])
        table.add_row(
            f"{scored.score:.3f}",
            scored.chunk.id,
            scored.chunk.kind.value,
            scored.source,
            " -> ".join(str(p) for p in path),
        )
    console.print(table)
    console.print(
        f"seeds={len(context.trace.get('seed_nodes', []))} "
        f"activated={context.trace.get('activated_nodes')} "
        f"inner={context.trace.get('inner_searcher')} "
        f"latency_ms={context.trace.get('latency_ms')}"
    )


def _print_counts(title: str, counts: dict[str, int]) -> None:
    table = Table(title=title)
    table.add_column("metric")
    table.add_column("count", justify="right")
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)


def _incident(graph: Any, node_id: str) -> list[tuple[str, str, str]]:
    rows = [
        (dst, str(data.get("kind", "")), "out")
        for _, dst, data in graph.out_edges(node_id, data=True)
    ]
    rows += [
        (src, str(data.get("kind", "")), "in")
        for src, _, data in graph.in_edges(node_id, data=True)
    ]
    return sorted(set(rows))


def _flatten(graph: Any) -> Any:
    """Copy the graph keeping only scalar attributes, which graphml and dot can represent."""
    import networkx as nx

    flat: nx.DiGraph[str] = nx.DiGraph()
    for node_id, data in graph.nodes(data=True):
        flat.add_node(
            node_id,
            kind=str(data.get("kind", "")),
            label=str(data.get("label", "")),
            course=str(data.get("course") or ""),
            lab_id=str(data.get("lab_id") or ""),
            chunks=len(data.get("chunk_ids", [])),
        )
    for src, dst, data in graph.edges(data=True):
        kind = str(data.get("kind", ""))
        flat.add_edge(src, dst, key=kind, kind=kind, weight=float(data.get("weight", 1)))
    return flat


def _to_dot(graph: Any) -> str:
    """Minimal Graphviz writer; avoids depending on pydot for a two-attribute export."""
    lines = ["digraph knowledge_graph {", "  rankdir=LR;"]
    for node_id, data in graph.nodes(data=True):
        label = str(data.get("label", node_id)).replace('"', "'")
        lines.append(f'  "{node_id}" [label="{label}", kind="{data.get("kind", "")}"];')
    for src, dst, data in graph.edges(data=True):
        lines.append(f'  "{src}" -> "{dst}" [label="{data.get("kind", "")}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"
