"""Database engine and session factory (PostgreSQL through psycopg 3)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def create_db_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # In-memory SQLite is used by unit tests: one shared connection, FK checks on.
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(database_url, pool_pre_ping=True)


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def ping(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
