"""
Role:   Read-only integration test of the eval stack against the shared corpus in Postgres.
Input:  DATABASE_URL from Settings; the chunks, embeddings and graph rows already indexed.
Output: pytest assertions; nothing is written to the database.
Flow:   Reads the prerequisites, then builds one tiny configuration (idf-weighted lexical
        searcher, the hierarchical chunks, the offline embedder) and runs three gold queries
        through it, asserting that the context is capped at k, carries real chunks and hits.
"""

import pytest

from rag_lab_generator.config import get_settings
from rag_lab_generator.eval import runner
from rag_lab_generator.eval.queries import load_queries

pytestmark = pytest.mark.integration

CONFIG = "vector/lexical_idf/hierarchical/fake"
QUERY_IDS: tuple[str, ...] = ("l1_readdir", "l2_zombie", "l5_mkfifo")
K = 5


def test_prerequisites_see_the_shared_corpus() -> None:
    prerequisites = runner.read_prerequisites(get_settings())
    assert prerequisites.chunks.get("hierarchical", 0) > 0
    assert prerequisites.graph_chunks.get("hierarchical", 0) > 0


def test_one_tiny_config_retrieves_relevant_context() -> None:
    settings = get_settings()
    spec = runner.spec_from_label(CONFIG, K)
    assert runner.read_prerequisites(settings).missing(spec) is None
    rag, _ = runner.build_rag(runner.settings_for(settings, spec), spec)
    gold = [q for q in load_queries() if q.id in QUERY_IDS]
    assert len(gold) == len(QUERY_IDS)
    results, _ = runner.run_config(rag, spec, gold, K)
    assert [r.query_id for r in results] == list(QUERY_IDS)
    for result in results:
        assert result.context.n_chunks == K
        assert result.context.total_chars > 0
        assert result.latency_ms > 0
    assert sum(r.hit for r in results) >= 2
