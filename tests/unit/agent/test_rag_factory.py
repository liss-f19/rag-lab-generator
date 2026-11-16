"""
Role:   Unit tests for the lazy retrieval factory used by the agent tools.
Input:  Settings fixture; no database connection is opened.
Output: Assertions; no side effects.
Flow:   Checks the store choice, that an unknown strategy becomes an actionable
        RagUnavailableError and that the cached factory builds the stack only once.
"""

import pytest

from rag_lab_generator.agent.rag_factory import (
    CachedRagFactory,
    RagUnavailableError,
    build_rag,
    build_store,
)
from rag_lab_generator.config import Settings
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

from .conftest import StubRAG


def test_build_store_returns_a_postgres_store(settings: Settings) -> None:
    assert isinstance(build_store(settings), PostgresStore)


def test_unknown_strategy_is_actionable(settings: Settings) -> None:
    with pytest.raises(RagUnavailableError) as excinfo:
        build_rag(settings.model_copy(update={"rag": "does-not-exist"}))
    assert "does-not-exist" in str(excinfo.value)


def test_factory_builds_only_once(settings: Settings) -> None:
    built: list[int] = []

    class Counting(CachedRagFactory):
        def __call__(self) -> StubRAG:
            if self._rag is None:
                built.append(1)
                self._rag = StubRAG(self.settings)
            assert isinstance(self._rag, StubRAG)
            return self._rag

    factory = Counting(settings)
    first, second = factory(), factory()
    assert first is second
    assert built == [1]
