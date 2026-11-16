"""
Role:   Typer sub-app exposing the agent as `rag-lab agent` and `rag-lab chat`.
Input:  CLI options (message, course, lab, llm provider, rag strategy, thread id).
Output: The agent answer rendered as markdown on the console.
Flow:   Both commands copy Settings with the CLI overrides, build the agent once and run turns
        through run_agent() on a shared thread id; retrieval and provider failures are printed
        as a short message instead of a traceback.
"""

from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown

from rag_lab_generator.agent.graph import AgentGraph, build_agent, run_agent
from rag_lab_generator.agent.rag_factory import RagUnavailableError, make_rag_factory
from rag_lab_generator.config import Settings, get_settings

app = typer.Typer(help="Interactive agent")
console = Console()

COURSE = typer.Option(None, "--course", help="restrict retrieval to sop1 or sop2")
LAB = typer.Option(None, "--lab", help="restrict retrieval to one lab id, e.g. sop1/l1")
PROVIDER = typer.Option(None, "--llm", help="llm provider: fake or anthropic")
RAG = typer.Option(None, "--rag", help="rag strategy: vector or graph")
THREAD = typer.Option("default", "--thread", help="conversation thread id for the memory saver")


@app.command()
def agent(
    message: str,
    course: str | None = COURSE,
    lab: str | None = LAB,
    llm: str | None = PROVIDER,
    rag: str | None = RAG,
    thread: str = THREAD,
) -> None:
    """Send one message to the agent and print the answer."""
    settings = _settings(llm, rag)
    graph = _build(settings)
    _turn(graph, message, thread, course, lab)


@app.command()
def chat(
    course: str | None = COURSE,
    lab: str | None = LAB,
    llm: str | None = PROVIDER,
    rag: str | None = RAG,
    thread: str = THREAD,
) -> None:
    """Talk to the agent in a REPL; the whole session shares one thread. /quit exits."""
    settings = _settings(llm, rag)
    graph = _build(settings)
    console.print(f"[bold]SOP assistant[/bold] (provider={settings.llm_provider}, thread={thread})")
    console.print("Type your question, /quit to leave.")
    while True:
        try:
            message = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if message in ("/quit", "/exit", "/q"):
            return
        if not message:
            continue
        _turn(graph, message, thread, course, lab)


def _settings(llm: str | None, rag: str | None) -> Settings:
    overrides: dict[str, Any] = {}
    if llm:
        overrides["llm_provider"] = llm
    if rag:
        overrides["rag"] = rag
    return get_settings().model_copy(update=overrides)


def _build(settings: Settings) -> AgentGraph:
    return build_agent(settings, rag_factory=make_rag_factory(settings, settings.rag))


def _turn(
    graph: AgentGraph, message: str, thread: str, course: str | None, lab: str | None
) -> None:
    # keep operational failures readable: the agent is a study tool, not a stack trace viewer
    try:
        answer = run_agent(graph, message, thread_id=thread, course=course, lab_id=lab)
    except RagUnavailableError as exc:
        console.print(f"[red]knowledge base unavailable:[/red] {exc}")
        return
    except RuntimeError as exc:
        console.print(f"[red]agent failed:[/red] {exc}")
        return
    console.print(Markdown(answer or "(empty answer)"))
