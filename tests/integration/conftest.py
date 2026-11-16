"""Integration fixtures: a dedicated PostgreSQL database and Redis.

TEST_DATABASE_URL must point to a throw-away database: the tests drop and
recreate the schema. TEST_REDIS_URL is optional; without it an in-process fake
Redis is used, which still exercises RQ end to end.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import fakeredis
import pytest
from alembic import command
from alembic.config import Config
from redis import Redis

from rag_lab_generator.cli import MIGRATIONS_DIR


@pytest.fixture(name="postgres_url", scope="session")
def postgres_url_fixture() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("TEST_DATABASE_URL does not point to PostgreSQL")
    return url


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(name="migrated_database")
def migrated_database_fixture(postgres_url: str) -> str:
    config = alembic_config(postgres_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return postgres_url


@pytest.fixture(name="redis_connection")
def redis_connection_fixture() -> Iterator[Redis]:
    url = os.environ.get("TEST_REDIS_URL")
    connection = Redis.from_url(url) if url else fakeredis.FakeRedis()
    connection.flushdb()
    yield connection
    connection.flushdb()
