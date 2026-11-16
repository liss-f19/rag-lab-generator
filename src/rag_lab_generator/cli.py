"""Command-line entry point: `rag-lab-generator <command>`.

Heavy modules (uvicorn, alembic, the container) are imported inside the
commands so that each command loads only what it needs.
"""

# pylint: disable=import-outside-toplevel

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from uuid import uuid4

from rag_lab_generator.config import get_settings
from rag_lab_generator.domain.models import User, UserRole

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _alembic_config():  # type: ignore[no-untyped-def]
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def _migrate(_args: argparse.Namespace) -> None:
    from alembic import command

    command.upgrade(_alembic_config(), "head")


def _api(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "rag_lab_generator.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
    )


def _worker(args: argparse.Namespace) -> None:
    from rag_lab_generator import worker

    worker.main(burst=args.burst)


def _create_user(args: argparse.Namespace) -> None:
    from rag_lab_generator.container import build_container

    container = build_container(get_settings())
    user = container.users.get_user_by_email(args.email)
    if user is None:
        user = User(
            user_id=uuid4(),
            email=args.email,
            display_name=args.name or args.email,
            role=UserRole(args.role),
        )
        container.users.add_user(user)
    elif user.role != UserRole(args.role):
        raise SystemExit(f"{args.email} already exists with role {user.role}")
    token = container.tokens.issue(user.user_id)
    print(
        json.dumps(
            {"user_id": str(user.user_id), "role": str(user.role), "token": token}
        )
    )


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    parser = argparse.ArgumentParser(prog="rag-lab-generator")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="apply database migrations").set_defaults(
        run=_migrate
    )

    api = commands.add_parser("api", help="run the HTTP API")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8000)
    api.set_defaults(run=_api)

    worker = commands.add_parser("worker", help="run the RQ worker")
    worker.add_argument(
        "--burst", action="store_true", help="exit when the queue is empty"
    )
    worker.set_defaults(run=_worker)

    user = commands.add_parser(
        "create-user", help="create a user (if missing) and print a bearer token"
    )
    user.add_argument("--email", required=True)
    user.add_argument("--name")
    user.add_argument(
        "--role", choices=[role.value for role in UserRole], required=True
    )
    user.set_defaults(run=_create_user)

    args = parser.parse_args(argv)
    args.run(args)
