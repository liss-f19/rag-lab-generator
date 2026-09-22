"""
Role:   Shared pytest fixtures for the ingestion unit tests.
Input:  Files under tests/fixtures/.
Output: Paths and Settings pointing at the fixture corpus; no network is ever used.
Flow:   Exposes the fixtures directory, single fixture pages and a Settings whose data_dir is
        the tiny corpus tree under tests/fixtures/corpus.
"""

from pathlib import Path

import pytest

from rag_lab_generator.config import Settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def example_task_page() -> Path:
    return FIXTURES / "example_task.en.md"


@pytest.fixture
def tutorial_page() -> Path:
    return FIXTURES / "tutorial_index.en.md"


@pytest.fixture
def corpus_settings() -> Settings:
    return Settings(data_dir=FIXTURES / "corpus")
