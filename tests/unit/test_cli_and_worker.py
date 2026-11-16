"""Command-line entry point and the worker's job entry point."""

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import fakeredis
import pytest
from sqlalchemy import create_engine

from rag_lab_generator import cli, worker
from rag_lab_generator.config import get_settings
from rag_lab_generator.infrastructure.orm import Base
from rag_lab_generator.infrastructure.security import TokenService
from tests.conftest import SIGNING_KEY, set_environment_variables


@pytest.fixture(name="sqlite_environment")
def sqlite_environment_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    database_url = "sqlite+pysqlite:///" + (tmp_path / "app.sqlite").as_posix()
    set_environment_variables(
        monkeypatch, tmp_path, DATABASE_URL=database_url, QUEUE_BACKEND="inline"
    )
    get_settings.cache_clear()
    Base.metadata.create_all(create_engine(database_url))
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("sqlite_environment")
def test_create_user_prints_a_valid_token(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["create-user", "--email", "anna@pw.edu.pl", "--role", "instructor"])
    first = json.loads(capsys.readouterr().out)
    assert first["role"] == "instructor"
    assert TokenService(SIGNING_KEY, 60).verify(first["token"]) == UUID(
        first["user_id"]
    )

    cli.main(["create-user", "--email", "anna@pw.edu.pl", "--role", "instructor"])
    assert json.loads(capsys.readouterr().out)["user_id"] == first["user_id"]

    with pytest.raises(SystemExit):
        cli.main(["create-user", "--email", "anna@pw.edu.pl", "--role", "student"])


def test_cli_dispatches_server_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        "uvicorn.run", lambda *args, **kwargs: calls.append(("api", kwargs))
    )
    monkeypatch.setattr(worker, "main", lambda burst: calls.append(("worker", burst)))
    monkeypatch.setattr(
        "alembic.command.upgrade", lambda config, rev: calls.append(("migrate", rev))
    )
    monkeypatch.setenv("TOKEN_SIGNING_KEY", SIGNING_KEY)
    get_settings.cache_clear()
    cli.main(["api", "--port", "9000"])
    cli.main(["worker", "--burst"])
    cli.main(["migrate"])
    get_settings.cache_clear()
    assert calls[0] == ("api", {"factory": True, "host": "0.0.0.0", "port": 9000})
    assert calls[1:] == [("worker", True), ("migrate", "head")]


def test_run_job_delegates_to_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    def run(job_id: UUID) -> SimpleNamespace:
        seen.append(job_id)
        return SimpleNamespace(status="succeeded")

    monkeypatch.setattr(worker, "_runner", lambda: SimpleNamespace(run=run))
    job_id = uuid4()
    assert worker.run_job(str(job_id)) == "succeeded"
    assert seen == [job_id]


def test_worker_main_drains_the_queue_in_burst_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = fakeredis.FakeRedis()
    monkeypatch.setenv("TOKEN_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.setattr(worker.Redis, "from_url", lambda url: connection)
    monkeypatch.setattr(worker, "_runner", lambda: None)
    get_settings.cache_clear()
    worker.main(burst=True)
    get_settings.cache_clear()
