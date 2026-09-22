"""
Role:   Evaluation endpoint: exposes the retrieval benchmark results to the web client.
Input:  results/*.csv written by `rag-lab eval` and the eval_runs table when the database is up.
Output: EvalRunsResponse with generically parsed csv rows and the stored runs.
Flow:   Lists every csv of settings.results_dir and parses it with csv.DictReader without
        assuming a column layout, then tries one SELECT on eval_runs; a missing table or an
        unreachable database only clears db_reachable instead of failing the request.
"""

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from rag_lab_generator.api import deps
from rag_lab_generator.api.schemas import EvalCsvFile, EvalDbRun, EvalRunsResponse
from rag_lab_generator.config import Settings

router = APIRouter(prefix="/api/eval", tags=["eval"])

MAX_ROWS = 500
MAX_RUNS = 200
SELECT_RUNS = "SELECT id, created_at, config, metrics FROM eval_runs ORDER BY id DESC LIMIT %s"


def settings_of(request: Request) -> Settings:
    state: Settings = request.app.state.settings
    return state


def _read_csv(path: Path) -> EvalCsvFile:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [
            {key: "" if value is None else str(value) for key, value in row.items() if key}
            for _, row in zip(range(MAX_ROWS), reader, strict=False)
        ]
    return EvalCsvFile(name=path.name, path=str(path), columns=columns, rows=rows)


def _csv_files(settings: Settings) -> list[EvalCsvFile]:
    directory = settings.results_dir
    if not directory.is_dir():
        return []
    files: list[EvalCsvFile] = []
    for path in sorted(directory.glob("*.csv")):
        try:
            files.append(_read_csv(path))
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
    return files


def _db_runs(settings: Settings) -> tuple[bool, list[EvalDbRun]]:
    try:
        store = deps.open_store(settings)
        with store.connection() as conn:
            rows = conn.execute(SELECT_RUNS, (MAX_RUNS,)).fetchall()
    except Exception:
        return False, []
    return True, [
        EvalDbRun(
            id=int(row["id"]),
            created_at=row["created_at"],
            config=_as_dict(row["config"]),
            metrics=_as_dict(row["metrics"]),
        )
        for row in rows
    ]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        loaded: Any = json.loads(value) if value else {}
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


@router.get("/runs", response_model=EvalRunsResponse)
async def runs(request: Request) -> EvalRunsResponse:
    """Every benchmark run known to the system: csv exports first, database rows second."""
    settings = settings_of(request)
    files = await run_in_threadpool(_csv_files, settings)
    reachable, db_runs = await run_in_threadpool(_db_runs, settings)
    return EvalRunsResponse(
        results_dir=str(settings.results_dir),
        db_reachable=reachable,
        files=files,
        db_runs=db_runs,
    )
