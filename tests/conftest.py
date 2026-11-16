"""Shared fixtures: an application container on in-memory SQLite and test doubles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from rag_lab_generator.api.app import create_app
from rag_lab_generator.application.jobs import JobRunner
from rag_lab_generator.config import Settings
from rag_lab_generator.container import Container, build_container, build_job_runner
from rag_lab_generator.domain.models import (
    IngestionStatus,
    Job,
    KnowledgeBaseRole,
    SourceDocument,
    User,
    UserRole,
)
from rag_lab_generator.infrastructure.db import create_db_engine
from rag_lab_generator.infrastructure.embeddings import HashingEmbeddingClient
from rag_lab_generator.infrastructure.orm import Base
from rag_lab_generator.infrastructure.queue import InlineJobQueue
from tests.fakes import InMemoryVectorIndex, RecordingQueue

SIGNING_KEY = "test-signing-key-" + "x" * 32


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "queue_backend": "inline",
        "embedding_provider": "hashing",
        "hashing_dimensions": 256,
        "token_signing_key": SIGNING_KEY,
        "file_storage_dir": tmp_path / "files",
        "chroma_persist_directory": tmp_path / "chroma",
        "chunk_max_chars": 400,
        "chunk_overlap_chars": 50,
        "max_upload_bytes": 64 * 1024,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@dataclass
class AppEnvironment:
    container: Container
    index: InMemoryVectorIndex
    queue: InlineJobQueue | RecordingQueue

    def add_user(self, role: UserRole) -> tuple[User, str]:
        user = User(
            user_id=uuid4(),
            email=f"{role}-{uuid4().hex[:8]}@example.edu",
            display_name=str(role),
            role=role,
        )
        self.container.users.add_user(user)
        return user, self.container.tokens.issue(user.user_id)

    def add_document(
        self, course_id: str, knowledge_base: KnowledgeBaseRole, **metadata: str
    ) -> SourceDocument:
        """Register a document directly in the repository (no file, no job)."""
        now = datetime.now(UTC)
        document = SourceDocument(
            document_id=uuid4(),
            course_id=course_id,
            knowledge_base=knowledge_base,
            filename="notes.md",
            media_type="text/markdown",
            storage_uri=f"file://{uuid4().hex}.md",
            checksum_sha256="0" * 64,
            metadata={"document_type": None, "topic": None, **metadata},
            ingestion_status=IngestionStatus.QUEUED,
            uploaded_by=None,
            created_at=now,
            updated_at=now,
        )
        self.container.documents.add_document(document)
        return document


def build_environment(tmp_path: Path, *, inline: bool = True) -> AppEnvironment:
    """Production wiring on in-memory SQLite, with an in-memory vector index.

    With inline=True jobs run during the request (as with QUEUE_BACKEND=inline);
    otherwise they are only recorded, as if no worker were running.
    """
    settings = make_settings(tmp_path)
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    index = InMemoryVectorIndex()
    runners: list[JobRunner] = []  # the runner needs the container's repositories

    def run_inline(job_id: UUID) -> Job:
        return runners[0].run(job_id)

    queue: InlineJobQueue | RecordingQueue = (
        InlineJobQueue(run_inline) if inline else RecordingQueue()
    )
    container = build_container(settings, engine=engine, queue=queue)
    runners.append(
        build_job_runner(
            settings,
            documents=container.documents,
            jobs=container.jobs,
            files=container.files,
            index=index,
            embedder=HashingEmbeddingClient(settings.hashing_dimensions),
        )
    )
    return AppEnvironment(container=container, index=index, queue=queue)


def set_environment_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: str
) -> None:
    """Configure get_settings() through the environment, as in deployment."""
    variables = {
        "TOKEN_SIGNING_KEY": SIGNING_KEY,
        "EMBEDDING_PROVIDER": "hashing",
        "FILE_STORAGE_DIR": str(tmp_path / "files"),
        "CHROMA_PERSIST_DIRECTORY": str(tmp_path / "chroma"),
        **overrides,
    }
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(tmp_path)  # a developer's .env file must not leak in


@pytest.fixture(name="env")
def env_fixture(tmp_path: Path) -> AppEnvironment:
    return build_environment(tmp_path)


@pytest.fixture(name="client")
def client_fixture(env: AppEnvironment) -> Iterator[TestClient]:
    with TestClient(create_app(env.container)) as test_client:
        yield test_client


@pytest.fixture(name="instructor_headers")
def instructor_headers_fixture(env: AppEnvironment) -> dict[str, str]:
    _, token = env.add_user(UserRole.INSTRUCTOR)
    return {"Authorization": f"Bearer {token}"}
