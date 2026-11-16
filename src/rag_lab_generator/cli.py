"""
Role:   Root Typer application; merges the sub-apps of every layer into one `rag-lab` command.
Input:  Command line arguments.
Output: Console output of the invoked sub-command; exit code 1 on a handled failure.
Flow:   Imports each layer's typer app and adds it without a name so its commands appear top-level;
        main() runs the app and converts known operational errors (database unreachable, unknown
        strategy, knowledge base unavailable, LLM call failure) into one-line messages.
"""

import psycopg
import typer
from rich.console import Console

from rag_lab_generator import __version__
from rag_lab_generator.agent.cli import app as agent_app
from rag_lab_generator.agent.rag_factory import RagUnavailableError
from rag_lab_generator.api.cli import app as api_app
from rag_lab_generator.eval.cli import app as eval_app
from rag_lab_generator.generation.llm.anthropic import LLMCallError
from rag_lab_generator.ingestion.cli import app as ingestion_app
from rag_lab_generator.registry import UnknownStrategyError
from rag_lab_generator.retrieval.cli import app as retrieval_app
from rag_lab_generator.retrieval.graph.cli import app as graph_app

app = typer.Typer(help="RAG lab generator", no_args_is_help=True, pretty_exceptions_enable=False)
app.add_typer(ingestion_app)
app.add_typer(retrieval_app)
app.add_typer(graph_app)
app.add_typer(agent_app)
app.add_typer(eval_app)
app.add_typer(api_app)

_HANDLED: tuple[type[Exception], ...] = (
    psycopg.OperationalError,
    UnknownStrategyError,
    RagUnavailableError,
    LLMCallError,
    FileNotFoundError,
)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


def main() -> None:
    try:
        app()
    except psycopg.OperationalError as exc:
        Console(stderr=True).print(
            f"[red]database unreachable:[/red] {str(exc).strip()}\n"
            "start it with `docker compose up -d db` and check DATABASE_URL in .env"
        )
        raise SystemExit(1) from exc
    except _HANDLED as exc:
        Console(stderr=True).print(f"[red]error:[/red] {exc}")
        raise SystemExit(1) from exc
