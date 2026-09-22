"""
Role:   End-to-end QA walk through the whole CLI pipeline with the deterministic fake providers.
Input:  A running Postgres (docker compose up -d db), the ingested corpus under data/raw.
Output: pytest assertions on exit codes and on the content of query / agent answers.
Flow:   run() shells out to `rag-lab` with EMBEDDING_PROVIDER=fake and LLM_PROVIDER=fake, a
        session fixture prepares the database (db-init, chunk, index, graph-build) once, and the
        individual tests exercise corpus-stats, every searcher, both RAG modes and the agent.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
STRATEGY = "hierarchical"
TIMINGS: dict[str, float] = {}


def _cli() -> list[str]:
    script = shutil.which("rag-lab")
    if script:
        return [script]
    return [sys.executable, "-m", "rag_lab_generator.cli"]


def run(
    *args: str, expect_ok: bool = True, extra_env: dict[str, str] | None = None, timeout: int = 900
) -> subprocess.CompletedProcess[str]:
    """Run the CLI with fake providers; record the wall time under the joined argument string."""
    env = dict(os.environ)
    env.update({"EMBEDDING_PROVIDER": "fake", "LLM_PROVIDER": "fake", "COLUMNS": "200"})
    if extra_env:
        env.update(extra_env)
    started = time.perf_counter()
    proc = subprocess.run(
        [*_cli(), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    TIMINGS[" ".join(args)] = time.perf_counter() - started
    if expect_ok and proc.returncode != 0:
        pytest.fail(
            f"`rag-lab {' '.join(args)}` exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc


def _output(proc: subprocess.CompletedProcess[str]) -> str:
    return f"{proc.stdout}\n{proc.stderr}"


def _assert_mentions(proc: subprocess.CompletedProcess[str], *needles: str) -> None:
    text = _output(proc).lower()
    missing = [n for n in needles if n.lower() not in text]
    assert not missing, f"answer misses {missing}\n--- output ---\n{_output(proc)[:4000]}"


@pytest.fixture(scope="module", autouse=True)
def prepared_database() -> None:
    """Schema, chunks, embeddings and graph for the hierarchical strategy, built once."""
    if not RAW_DIR.is_dir():
        pytest.skip(f"{RAW_DIR} missing: run `rag-lab ingest` first")
    run("db-init")
    run("chunk", "--strategy", STRATEGY)
    run("index", "--embedder", "fake", "--strategy", STRATEGY)
    run("graph-build", "--strategy", STRATEGY)


# ------------------------------------------------------------------ cli surface


def test_help_lists_every_command() -> None:
    proc = run("--help")
    text = _output(proc)
    for command in (
        "ingest",
        "corpus-stats",
        "db-init",
        "db-stats",
        "chunk",
        "index",
        "query",
        "graph-build",
        "graph-stats",
        "graph-query",
        "agent",
    ):
        assert command in text, f"`rag-lab --help` does not list {command!r}:\n{text}"


def test_corpus_stats_reports_twelve_labs() -> None:
    proc = run("corpus-stats")
    assert "12" in _output(proc), f"corpus-stats does not report 12 labs:\n{_output(proc)}"


def test_db_stats_reports_chunks_and_embeddings() -> None:
    proc = run("db-stats")
    text = _output(proc).lower()
    assert "chunk" in text and "embedding" in text, text


# ------------------------------------------------------------------ chunking strategies


@pytest.mark.parametrize("strategy", ["hierarchical", "fixed", "semantic"])
def test_chunk_every_strategy(strategy: str) -> None:
    proc = run("chunk", "--strategy", strategy)
    assert _output(proc).strip(), f"chunk --strategy {strategy} printed nothing"


def test_chunking_is_idempotent() -> None:
    """Re-chunking the same strategy must replace, not duplicate."""
    first = run("chunk", "--strategy", STRATEGY)
    second = run("chunk", "--strategy", STRATEGY)
    assert _digits(first) == _digits(second), (
        f"chunk counts differ between runs\nfirst:\n{_output(first)}\nsecond:\n{_output(second)}"
    )


def _digits(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return re.findall(r"\d+", _output(proc))


# ------------------------------------------------------------------ retrieval


READDIR_QUERY = "how to read directory entries with readdir"
EPOLL_QUERY = "how does epoll differ from select"
# The CLI prints lab ids (sop1/l1), never folder slugs; the fake embedder hashes text into
# random vectors, so only the searchers with a lexical side can be expected to find a lab.
FILESYSTEM_LAB = "sop1/l1"
EPOLL_LAB = "sop2/l7"


@pytest.mark.parametrize("searcher", ["lexical_idf", "hybrid_rrf_idf"])
def test_query_finds_the_filesystem_lab(searcher: str) -> None:
    proc = run(
        "query",
        READDIR_QUERY,
        "--rag",
        "vector",
        "--searcher",
        searcher,
        "--strategy",
        STRATEGY,
        "--embedder",
        "fake",
    )
    assert FILESYSTEM_LAB in _output(proc), (
        f"searcher {searcher} did not surface {FILESYSTEM_LAB}:\n{_output(proc)[:4000]}"
    )


def test_lexical_search_actually_matches_the_term() -> None:
    proc = run(
        "query",
        READDIR_QUERY,
        "--rag",
        "vector",
        "--searcher",
        "lexical",
        "--strategy",
        STRATEGY,
        "--embedder",
        "fake",
    )
    _assert_mentions(proc, "readdir")


def test_graph_rag_answers_the_epoll_question() -> None:
    proc = run(
        "query",
        EPOLL_QUERY,
        "--rag",
        "graph",
        "--strategy",
        STRATEGY,
        "--embedder",
        "fake",
    )
    assert EPOLL_LAB in _output(proc), _output(proc)[:4000]


def test_graph_query_command() -> None:
    proc = run("graph-query", EPOLL_QUERY, "--embedder", "fake")
    assert EPOLL_LAB in _output(proc), _output(proc)[:4000]


def test_graph_stats_reports_nodes_and_edges() -> None:
    proc = run("graph-stats")
    text = _output(proc).lower()
    assert "node" in text and "edge" in text, text


# ------------------------------------------------------------------ agent


@pytest.mark.parametrize("rag", ["vector", "graph"])
def test_agent_generates_a_lab(rag: str) -> None:
    proc = run(
        "agent",
        "generate a lab about FIFO similar to L5",
        "--llm",
        "fake",
        "--rag",
        rag,
        "--course",
        "sop2",
    )
    _assert_mentions(proc, "fifo")


def test_agent_explains_a_topic() -> None:
    proc = run("agent", "explain what a zombie process is", "--llm", "fake")
    _assert_mentions(proc, "zombie")


def test_agent_visualizes_a_concept() -> None:
    proc = run("agent", "visualize fork exec wait lifecycle", "--llm", "fake")
    assert _output(proc).strip(), "agent produced no visualization output"


# ------------------------------------------------------------------ robustness


def test_unreachable_database_reports_a_clean_error() -> None:
    """A down database must produce a one-line message, never a raw traceback."""
    proc = run(
        "query",
        READDIR_QUERY,
        "--strategy",
        STRATEGY,
        "--embedder",
        "fake",
        expect_ok=False,
        extra_env={"DATABASE_URL": "postgresql://rag:rag@localhost:5999/raglab"},
        timeout=120,
    )
    text = _output(proc)
    assert proc.returncode != 0, f"unreachable database still exited 0:\n{text}"
    assert "Traceback (most recent call last)" not in text, f"raw traceback leaked:\n{text}"


def test_unknown_strategy_reports_available_names() -> None:
    proc = run(
        "query",
        READDIR_QUERY,
        "--strategy",
        STRATEGY,
        "--embedder",
        "fake",
        "--searcher",
        "nonexistent",
        expect_ok=False,
        timeout=120,
    )
    text = _output(proc)
    assert proc.returncode != 0, f"unknown searcher still exited 0:\n{text}"
    assert "Traceback (most recent call last)" not in text, f"raw traceback leaked:\n{text}"
    assert "hybrid_rrf" in text, f"error does not list the available searchers:\n{text}"


def test_agent_without_chunks_reports_a_clean_error() -> None:
    """Querying a strategy that was never chunked must not crash the agent."""
    proc = run(
        "agent",
        "generate a lab about FIFO similar to L5",
        "--llm",
        "fake",
        "--rag",
        "vector",
        expect_ok=False,
        extra_env={"CHUNKER": "nonexistent"},
        timeout=300,
    )
    assert "Traceback (most recent call last)" not in _output(proc), _output(proc)
