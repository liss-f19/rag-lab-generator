"""
Role:   Unit tests for the pure metric functions with hand-computed expectations.
Input:  Chunks built by the local conftest factories.
Output: pytest assertions.
Flow:   Checks target matching (including the l5 / l5_5 prefix trap), then every scalar metric on
        a fixed relevance pattern, then the context statistics and the run-level aggregation.
"""

from math import log2

import pytest

from rag_lab_generator.eval import metrics
from rag_lab_generator.eval.queries import EvalQueryFile
from rag_lab_generator.models import ChunkKind
from tests.unit.eval.conftest import build_chunk, build_ranked


def test_matches_target_exact_id_and_child_documents() -> None:
    assert metrics.matches_target(build_chunk("sop1/l1"), "sop1/l1")
    assert metrics.matches_target(build_chunk("sop1/l1/summary"), "sop1/l1")
    assert metrics.matches_target(build_chunk("sop2/lecture/vmem/index"), "sop2/lecture/vmem")


def test_matches_target_does_not_confuse_l5_with_l5_5() -> None:
    assert not metrics.matches_target(build_chunk("sop2/l5_5"), "sop2/l5")
    assert not metrics.matches_target(build_chunk("sop2/l5_5", lab_id="sop2/l5_5"), "sop2/l5")


def test_matches_target_uses_lab_id_of_external_documents() -> None:
    chunk = build_chunk("external/kozlowski/tcpip/lecture_4@sop2/l8", lab_id="sop2/l8")
    assert metrics.matches_target(chunk, "sop2/l8")


def test_scalar_metrics_on_a_fixed_relevance_pattern() -> None:
    flags = [False, True, False, True]
    assert metrics.hit_at_k(flags) == 1.0
    assert metrics.first_relevant_rank(flags) == 2
    assert metrics.mrr(flags) == pytest.approx(0.5)
    dcg = 1 / log2(3) + 1 / log2(5)
    idcg = 1 / log2(2) + 1 / log2(3) + 1 / log2(4) + 1 / log2(5)
    assert metrics.ndcg_at_k(flags, 4) == pytest.approx(dcg / idcg)
    assert metrics.ndcg_at_k(flags, 4) == pytest.approx(0.41443, abs=1e-5)


def test_empty_result_scores_zero() -> None:
    assert metrics.hit_at_k([]) == 0.0
    assert metrics.mrr([]) == 0.0
    assert metrics.first_relevant_rank([]) is None
    assert metrics.ndcg_at_k([], 8) == 0.0


def test_recall_and_coverage_count_distinct_targets() -> None:
    chunks = build_ranked([build_chunk("sop1/l1"), build_chunk("sop1/l1/summary")])
    assert metrics.recall_at_k(chunks, ["sop1/l1", "sop1/l2"]) == pytest.approx(0.5)
    assert metrics.coverage(chunks, ["sop1/l1"]) == 1.0
    assert metrics.recall_at_k(chunks, []) == 0.0


def test_section_recall_counts_document_scoped_sections() -> None:
    chunks = build_ranked(
        [
            build_chunk("sop1/l1", section_id="browsing-a-directory"),
            build_chunk("sop1/l2", section_id="file-operations"),
        ]
    )
    expected = ["sop1/l1#browsing-a-directory", "sop1/l1#file-operations"]
    assert metrics.section_recall_at_k(chunks, expected) == pytest.approx(0.5)
    assert metrics.section_recall_at_k(chunks, []) is None


def test_context_stats_counts_chars_documents_and_kinds() -> None:
    chunks = build_ranked(
        [
            build_chunk("sop1/l1", text="abcd"),
            build_chunk("sop1/l1", idx=1, text="ef", kind=ChunkKind.TASK),
            build_chunk("sop1/l2", idx=0, text="ghi", kind=ChunkKind.TASK),
        ]
    )
    stats = metrics.context_stats(chunks)
    assert stats.n_chunks == 3
    assert stats.total_chars == 9
    assert stats.distinct_documents == 2
    assert stats.kinds == {"task": 2, "tutorial": 1}


def test_context_stats_labels_the_support_of_every_chunk() -> None:
    chunks = build_ranked(
        [
            build_chunk("sop1/l1", text="ab"),
            build_chunk("external/kozlowski/unix/06-files", text="cd"),
            build_chunk("sop1/l9", text="ef"),
        ]
    )
    support = {"sop1/l1": "primary", "external/kozlowski/unix/06-files": "background"}
    stats = metrics.context_stats(chunks, support)
    assert stats.support == {"background": 1, "primary": 1, "unknown": 1}
    assert metrics.context_stats(chunks).support == {"unknown": 3}


def test_aggregate_reports_the_support_mix() -> None:
    query = EvalQueryFile(id="q", query="q", expected_lab_ids=["sop1/l1"])
    support = {"sop1/l1": "primary", "sop1/l2": "background"}
    first = metrics.query_metrics(build_ranked([build_chunk("sop1/l1")]), query, 1, 1.0, support)
    second = metrics.query_metrics(build_ranked([build_chunk("sop1/l2")]), query, 1, 1.0, support)
    aggregated = metrics.aggregate([first, second])
    assert aggregated.support_distribution == {"background": 0.5, "primary": 0.5}


def test_query_metrics_truncates_to_k() -> None:
    query = EvalQueryFile(
        id="q1",
        query="how to list a directory",
        expected_lab_ids=["sop1/l1"],
        expected_section_ids=["sop1/l1#browsing-a-directory"],
    )
    chunks = build_ranked(
        [
            build_chunk("sop1/l2"),
            build_chunk("sop1/l1", section_id="browsing-a-directory"),
            build_chunk("sop1/l1", idx=2),
        ]
    )
    result = metrics.query_metrics(chunks, query, k=1)
    assert result.hit == 0.0
    assert result.first_relevant_rank is None
    assert result.recall_at_k == 0.0
    assert result.section_recall_at_k == 0.0
    assert metrics.query_metrics(chunks, query, k=3).first_relevant_rank == 2


def test_percentile_uses_nearest_rank() -> None:
    assert metrics.percentile([50.0, 10.0, 30.0, 20.0, 40.0], 0.5) == 30.0
    assert metrics.percentile([], 0.5) == 0.0


def test_aggregate_averages_every_query() -> None:
    query = EvalQueryFile(id="q", query="q", expected_lab_ids=["sop1/l1"])
    hit = metrics.query_metrics(build_ranked([build_chunk("sop1/l1", text="ab")]), query, 1, 10.0)
    miss = metrics.query_metrics(
        build_ranked([build_chunk("sop1/l2", text="abcd")]), query, 1, 30.0
    )
    aggregated = metrics.aggregate([hit, miss])
    assert aggregated.n_queries == 2
    assert aggregated.hit_at_k == pytest.approx(0.5)
    assert aggregated.recall_at_k == pytest.approx(0.5)
    assert aggregated.mrr == pytest.approx(0.5)
    assert aggregated.latency_ms_mean == pytest.approx(20.0)
    assert aggregated.latency_ms_p50 == pytest.approx(10.0)
    assert aggregated.latency_ms_p50_warm == pytest.approx(30.0)
    assert aggregated.latency_ms_first == pytest.approx(10.0)
    assert aggregated.context_chars_mean == pytest.approx(3.0)
    assert aggregated.n_section_queries == 0
    assert aggregated.kind_distribution == {"tutorial": 1.0}
