"""
Role:   Typer sub-app with the API commands; merged into the root CLI as `rag-lab serve`.
Input:  CLI options (host, port, reload).
Output: A running uvicorn server exposing the FastAPI application.
Flow:   serve() hands uvicorn the application factory as an import string so --reload can
        re-import it after a file change.
"""

import typer

app = typer.Typer(help="HTTP API for the web client")

APP_IMPORT = "rag_lab_generator.api.app:app_factory"


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="bind address"),
    port: int = typer.Option(8000, help="bind port"),
    reload: bool = typer.Option(False, help="restart on source changes"),
) -> None:
    """Run the FastAPI backend consumed by the web client."""
    import uvicorn  # heavy optional dependency, loaded only by `serve`

    uvicorn.run(APP_IMPORT, host=host, port=port, reload=reload, factory=True)
