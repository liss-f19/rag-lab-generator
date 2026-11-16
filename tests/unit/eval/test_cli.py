"""
Role:   Unit tests for the eval CLI: option wiring, validation exit codes and the judge command.
Input:  typer CliRunner; run_matrix, corpus_index and judge_lab monkeypatched away.
Output: pytest assertions.
Flow:   Invokes `eval` with --config and --matrix and inspects the configurations handed to
        run_matrix, checks the error paths (bad label, no selection, unknown gold id) and runs
        `judge` on a temporary markdown file with a stubbed judge.
"""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rag_lab_generator.eval import cli
from rag_lab_generator.eval.judge import JudgeResult, JudgeScores
from rag_lab_generator.eval.metrics import EvalMetricsFull
from rag_lab_generator.eval.queries import CorpusIndex
from rag_lab_generator.models import EvalRun

runner = CliRunner()


def _fake_run(captured: list[Any]) -> Any:
    def run_matrix(
        settings: Any, configs: list[Any], queries: list[Any], k: int, *a: Any, **kw: Any
    ):
        captured.append((configs, queries, k))
        return [
            EvalRun(
                config=configs[0],
                metrics=EvalMetricsFull(
                    recall_at_k=1.0,
                    mrr=1.0,
                    ndcg_at_k=1.0,
                    latency_ms_p50=1.0,
                    n_queries=len(queries),
                ),
            )
        ]

    return run_matrix


def test_eval_single_config_runs_one_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Any] = []
    monkeypatch.setattr(cli.runner, "run_matrix", _fake_run(captured))
    result = runner.invoke(
        cli.app,
        ["eval", "--config", "graph/dense/hierarchical/bge_m3", "-k", "4", "--tag", "lang:pl"],
    )
    assert result.exit_code == 0, result.output
    configs, queries, k = captured[0]
    assert len(configs) == 1 and configs[0].inner_searcher == "dense"
    assert k == 4 and all("lang:pl" in q.tags for q in queries)


def test_eval_matrix_expands_the_requested_axes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Any] = []
    monkeypatch.setattr(cli.runner, "run_matrix", _fake_run(captured))
    result = runner.invoke(
        cli.app,
        ["eval", "--matrix", "--chunker", "fixed", "--searcher", "lexical", "--embedder", "fake"],
    )
    assert result.exit_code == 0, result.output
    configs = captured[0][0]
    assert {c.label for c in configs} == {"vector/lexical/fixed/fake", "graph/lexical/fixed/fake"}


def test_eval_without_a_mode_or_with_a_bad_label_exits_one() -> None:
    assert runner.invoke(cli.app, ["eval"]).exit_code == 1
    bad = runner.invoke(cli.app, ["eval", "--config", "vector/nope/fixed/fake"])
    assert bad.exit_code == 1 and "unknown searcher" in bad.output


def test_eval_queries_reports_unknown_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "corpus_index", lambda _s: CorpusIndex(document_ids={"sop1/l1"}))
    result = runner.invoke(cli.app, ["eval-queries"])
    assert result.exit_code == 1
    assert "unknown ids" in result.output


def test_eval_queries_accepts_a_complete_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    every = CorpusIndex()
    for query in cli.load_queries():
        every.document_ids.update(query.targets)
        every.lab_ids.update(query.expected_lab_ids)
        every.section_keys.update(query.expected_section_ids)
    monkeypatch.setattr(cli, "corpus_index", lambda _s: every)
    result = runner.invoke(cli.app, ["eval-queries", "--show"])
    assert result.exit_code == 0
    assert "every expected id exists" in result.output


def test_judge_command_prints_the_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "lab.md"
    path.write_text("# Generated lab", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "judge_lab",
        lambda *a, **kw: JudgeResult(
            scores=JudgeScores(style_match=5), model="fake", prompt="p", parsed=True
        ),
    )
    result = runner.invoke(cli.app, ["judge", str(path)])
    assert result.exit_code == 0
    assert "style_match" in result.output
