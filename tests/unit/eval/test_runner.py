"""
Role:   Unit tests for the matrix runner with a stub RAG, so no database is touched.
Input:  Settings fixture, stub retrieval results, tmp_path for the csv output.
Output: pytest assertions.
Flow:   Checks the shape of the default matrix and the label parser, the prerequisite rules
        (skip and offline-embedder fallback), the top-k truncation and one full run_matrix pass
        with read_prerequisites, build_rag and insert_runs monkeypatched away.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.eval import runner
from rag_lab_generator.eval.queries import EvalQueryFile
from rag_lab_generator.models import EvalConfig, RetrievedContext, ScoredChunk
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from tests.unit.eval.conftest import build_chunk


class StubRAG(RAG):
    """Returns a canned ranking and records the filters it was called with."""

    name = "stub"

    def __init__(self, chunks: list[ScoredChunk]) -> None:
        self.chunks = chunks
        self.calls: list[SearchFilters] = []

    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext:
        self.calls.append(filters)
        return RetrievedContext(
            query=query, rag=self.name, chunks=self.chunks, trace={"inner_searcher": "lexical"}
        )


GOLD = [
    EvalQueryFile(
        id="q1", query="how to list a directory", expected_lab_ids=["sop1/l1"], tags=["course:sop1"]
    ),
    EvalQueryFile(id="q2", query="what is a zombie process", expected_lab_ids=["sop1/l2"]),
]


def _stub_chunks() -> list[ScoredChunk]:
    return [
        ScoredChunk(chunk=build_chunk("sop1/l2"), score=0.4, source="stub"),
        ScoredChunk(chunk=build_chunk("sop1/l1"), score=0.9, source="stub"),
    ]


def test_default_matrix_is_every_rag_times_searcher_times_chunker() -> None:
    configs = runner.default_matrix(8)
    searchers = [name for name, _ in runner.SEARCHER_RECIPES]
    assert len(configs) == 2 * len(searchers) * len(runner.DEFAULT_CHUNKERS)
    assert {c.label for c in configs if c.rag == "graph"} == {
        f"graph/{s}/{c}/bge_m3" for s in searchers for c in runner.DEFAULT_CHUNKERS
    }


def test_graph_configs_wrap_the_compared_searcher_as_the_walker_seed() -> None:
    graph = [c for c in runner.default_matrix(8) if c.rag == "graph"]
    assert {c.searcher for c in graph} == {"graph_walk"}
    assert {c.inner_searcher for c in graph} == {n for n, _ in runner.SEARCHER_RECIPES}
    assert all(c.needs_graph for c in graph)


def test_build_configs_sweeps_hops_without_duplicating_the_vector_rows() -> None:
    configs = runner.build_configs(8, ["hierarchical"], ["fake"], hops_values=[1, 2, 3])
    assert sorted({c.hops for c in configs if c.rag == "graph"}) == [1, 2, 3]
    assert len([c for c in configs if c.rag == "vector"]) == len(runner.SEARCHER_RECIPES)


def test_spec_from_label_round_trips_and_rejects_nonsense() -> None:
    spec = runner.spec_from_label("graph/hybrid_rrf/hierarchical/bge_m3", 8, hops=3)
    assert (spec.searcher, spec.inner_searcher, spec.hops) == ("graph_walk", "hybrid_rrf", 3)
    assert spec.label == "graph/hybrid_rrf/hierarchical/bge_m3"
    assert runner.spec_from_label("vector/lexical/fixed/fake", 4).hops is None
    with pytest.raises(ValueError):
        runner.spec_from_label("vector/lexical/fixed", 4)
    with pytest.raises(ValueError):
        runner.spec_from_label("nosuchrag/lexical/fixed/fake", 4)


def test_prerequisites_report_the_missing_piece() -> None:
    spec = runner.spec_from_label("graph/dense/hierarchical/bge_m3", 8)
    assert "no chunks" in str(runner.Prerequisites().missing(spec))
    have_chunks = runner.Prerequisites(chunks={"hierarchical": 10})
    assert "embeddings" in str(have_chunks.missing(spec))
    have_vectors = runner.Prerequisites(
        chunks={"hierarchical": 10}, vectors={"bge_m3/hierarchical": 10}
    )
    assert "graph" in str(have_vectors.missing(spec))
    complete = runner.Prerequisites(
        chunks={"hierarchical": 10},
        vectors={"bge_m3/hierarchical": 10},
        graph_chunks={"hierarchical": 5},
    )
    assert complete.missing(spec) is None


def test_resolve_falls_back_to_the_offline_embedder_with_a_warning() -> None:
    spec = runner.spec_from_label("vector/dense/hierarchical/bge_m3", 8)
    prerequisites = runner.Prerequisites(
        chunks={"hierarchical": 10}, vectors={"fake/hierarchical": 10}
    )
    warnings: list[str] = []
    resolved = runner.resolve(spec, prerequisites, warnings.append)
    assert resolved is not None and resolved.embedder == "fake"
    assert "FALLING BACK" in warnings[0]


def test_resolve_skips_when_nothing_can_replace_the_missing_piece() -> None:
    spec = runner.spec_from_label("vector/lexical/semantic/fake", 8)
    warnings: list[str] = []
    assert runner.resolve(spec, runner.Prerequisites(), warnings.append) is None
    assert "skipped" in warnings[0]


def test_top_k_sorts_by_score_and_drops_the_expansion_tail() -> None:
    context = RetrievedContext(query="q", rag="vector", chunks=_stub_chunks())
    top = runner.top_k(context, 1)
    assert [sc.chunk.document_id for sc in top] == ["sop1/l1"]


def test_run_config_passes_the_course_filter_only_when_asked() -> None:
    rag = StubRAG(_stub_chunks())
    spec = runner.spec_from_label("vector/lexical/hierarchical/fake", 2)
    results, inner = runner.run_config(rag, spec, GOLD, 2)
    assert [r.query_id for r in results] == ["q1", "q2"]
    assert inner == "lexical"
    assert [f.course for f in rag.calls] == [None, None]
    assert all(f.strategy == "hierarchical" for f in rag.calls)
    filtered = StubRAG(_stub_chunks())
    runner.run_config(filtered, spec, GOLD, 2, filter_course=True)
    assert [f.course for f in filtered.calls] == ["sop1", None]


def test_run_matrix_writes_csv_json_and_skips_impossible_configs(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runner,
        "read_prerequisites",
        lambda _s: runner.Prerequisites(
            chunks={"hierarchical": 1}, vectors={"fake/hierarchical": 1}
        ),
    )
    monkeypatch.setattr(runner, "build_rag", lambda _s, _spec: (StubRAG(_stub_chunks()), None))
    inserted: list[Any] = []
    monkeypatch.setattr(runner, "insert_runs", lambda _s, runs: inserted.extend(runs))
    configs: list[EvalConfig] = [
        runner.spec_from_label("vector/lexical/hierarchical/fake", 2),
        runner.spec_from_label("vector/lexical/fixed/fake", 2),
    ]
    runs = runner.run_matrix(settings, configs, GOLD, 2, tmp_path)
    assert len(runs) == 1
    assert runs[0].metrics.n_queries == 2
    assert len(inserted) == 1
    payload = json.loads((tmp_path / "eval_latest.json").read_text(encoding="utf-8"))
    assert payload[0]["config"]["chunker"] == "hierarchical"
    assert payload[0]["metrics"]["hit_at_k"] == 1.0
    per_query = next(tmp_path.glob("eval_*_per_query.csv")).read_text(encoding="utf-8")
    assert per_query.count("\n") == 3
    assert "query_id" in per_query
    summary = next(p for p in tmp_path.glob("eval_*.csv") if "per_query" not in p.name)
    assert "ndcg_at_k" in summary.read_text(encoding="utf-8")
