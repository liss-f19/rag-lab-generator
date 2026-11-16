"""
Role:   Fixtures for the API unit tests: a throwaway corpus tree and a TestClient.
Input:  pytest tmp_path; the lab.xml fixture next to this file.
Output: Settings pointing at the temporary data dir, and a TestClient over create_app().
Flow:   corpus_dir() builds data/raw/sop1/l1_filesystem with lab.xml, summary.md, manifest.json
        and one source file; settings() points data_dir there and the database at a closed port
        so every database-backed route fails fast with 503 instead of hanging.
"""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_lab_generator.api.app import create_app
from rag_lab_generator.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
COURSE = "sop1"
SLUG = "l1_filesystem"
UNREACHABLE_DB = "postgresql://rag:rag@127.0.0.1:1/raglab"


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    """Minimal data/ tree with one complete lab folder."""
    lab = tmp_path / "raw" / COURSE / SLUG
    (lab / "src").mkdir(parents=True)
    (lab / "slides").mkdir()
    shutil.copy(FIXTURES / "lab.xml", lab / "lab.xml")
    (lab / "summary.md").write_text("# Filesystem API\n\nopendir, readdir, stat.\n", "utf-8")
    (lab / "manifest.json").write_text(
        json.dumps({"lab_id": f"{COURSE}/{SLUG}", "course": COURSE, "slug": SLUG}), "utf-8"
    )
    (lab / "src" / "prog1.c").write_text("int main(void) { return 0; }\n", "utf-8")
    (tmp_path / "raw" / COURSE / "empty").mkdir()
    return tmp_path


@pytest.fixture
def settings(corpus_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        data_dir=corpus_dir,
        results_dir=tmp_path / "results",
        database_url=UNREACHABLE_DB,
        embedding_provider="fake",
        llm_provider="fake",
    )


@pytest.fixture
def empty_settings(tmp_path: Path) -> Settings:
    """Settings whose data dir, results dir and database are all missing."""
    return Settings(
        data_dir=tmp_path / "missing",
        results_dir=tmp_path / "missing-results",
        database_url=UNREACHABLE_DB,
        embedding_provider="fake",
        llm_provider="fake",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def empty_client(empty_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(empty_settings)) as test_client:
        yield test_client
