"""
Role:   Unit tests for the reciprocal rank fusion math and the SQL filter translation.
Input:  Synthetic rank lists and SearchFilters instances; no database.
Output: Assertions; no side effects.
Flow:   Checks the RRF score formula, ordering, rank bookkeeping, the idf weight curve, the two
        registered hybrid variants and how SearchFilters become WHERE clauses with parameters.
"""

from typing import Any

import pytest

from rag_lab_generator import registry
from rag_lab_generator.config import Settings
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.searchers.hybrid_rrf import rrf_fuse
from rag_lab_generator.retrieval.stores.vector_store import _filter_sql, _idf


def test_rrf_scores_follow_the_formula() -> None:
    fused = rrf_fuse({"lexical": ["a", "b"], "dense": ["b", "c"]}, rrf_k=60)
    scores = {chunk_id: score for chunk_id, score, _ in fused}
    assert scores["a"] == 1 / 61
    assert scores["b"] == 1 / 62 + 1 / 61
    assert scores["c"] == 1 / 62


def test_rrf_ranks_documents_found_by_both_sources_first() -> None:
    fused = rrf_fuse({"lexical": ["a", "b"], "dense": ["b", "c"]}, rrf_k=60)
    assert [chunk_id for chunk_id, _, _ in fused][0] == "b"


def test_rrf_keeps_per_source_ranks() -> None:
    fused = rrf_fuse({"lexical": ["a", "b"], "dense": ["b"]}, rrf_k=10)
    ranks = {chunk_id: rank for chunk_id, _, rank in fused}
    assert ranks["b"] == {"lexical": 2, "dense": 1}
    assert ranks["a"] == {"lexical": 1}


def test_rrf_is_stable_for_equal_scores() -> None:
    fused = rrf_fuse({"lexical": ["b", "a"]}, rrf_k=1)
    assert [chunk_id for chunk_id, _, _ in fused] == ["b", "a"]


def test_searchers_are_registered() -> None:
    expected = {"lexical", "lexical_idf", "dense", "hybrid_rrf", "hybrid_rrf_idf"}
    assert expected.issubset(registry.available("searcher"))


def test_hybrid_variants_pick_their_lexical_side() -> None:
    plain = registry.get("searcher", "hybrid_rrf")
    idf = registry.get("searcher", "hybrid_rrf_idf")
    assert plain.lexical_name == "lexical"  # type: ignore[attr-defined]
    assert idf.lexical_name == "lexical_idf"  # type: ignore[attr-defined]
    assert issubclass(idf, plain)


def test_idf_is_higher_for_rarer_terms() -> None:
    rare = _idf(1000, 5)
    common = _idf(1000, 500)
    assert rare > common > 1.0
    assert _idf(1000, 1000) == pytest.approx(1.0, abs=1e-3)


def test_filter_sql_translates_every_field() -> None:
    filters = SearchFilters(strategy="hierarchical", course="sop1", lab_id="l1", kinds=["task"])
    clauses, params = _filter_sql(filters, "c")
    assert clauses == [
        "c.strategy = %s",
        "c.course = %s",
        "c.lab_id = %s",
        "c.kind = ANY(%s)",
    ]
    assert params == ["hierarchical", "sop1", "l1", ["task"]]


def test_filter_sql_requires_only_the_strategy() -> None:
    clauses, params = _filter_sql(SearchFilters(strategy="fixed"), "c")
    assert clauses == ["c.strategy = %s"]
    assert params == ["fixed"]


class _AliasEmbedder(Embedder):
    name = "remote"
    space = "local"

    @property
    def dim(self) -> int:
        return 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class _RecordingStore:
    """Stands in for VectorStore: records the dense_search arguments, returns no chunks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls: list[tuple[Any, ...]] = []

    def dense_search(self, *args: Any) -> list[tuple[str, float]]:
        self.calls.append(args)
        return []

    def fetch_chunks(self, ids: list[str]) -> dict[str, Any]:
        return {}


def test_dense_searcher_queries_the_embedder_vector_space() -> None:
    settings = Settings(embedding_provider="fake")
    store = _RecordingStore(settings)
    searcher = registry.create(
        "searcher", "dense", store=store, embedder=_AliasEmbedder(settings), settings=settings
    )
    searcher.vectors = store
    assert searcher.search("q", 3, SearchFilters(strategy="hierarchical")) == []
    assert store.calls[0][1] == "local"
