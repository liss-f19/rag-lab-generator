"""
Role:   Unit tests for the gold query file: its shape, its coverage and the id validator.
Input:  The packaged eval/queries.yaml and hand-built CorpusIndex instances.
Output: pytest assertions.
Flow:   Loads the shipped gold set and asserts the thesis requirements (size, one tag family per
        query, at least three queries per laboratory, Polish queries, section id encoding), then
        exercises validate_queries and the duplicate-id guard on temporary files.
"""

from collections import Counter
from pathlib import Path

import pytest

from rag_lab_generator.eval.queries import (
    CorpusIndex,
    EvalQueryFile,
    corpus_index,
    filter_by_tag,
    load_queries,
    validate_queries,
)

LABS: tuple[str, ...] = (
    "sop1/l0",
    "sop1/l1",
    "sop1/l2",
    "sop1/l3",
    "sop1/l4",
    "sop1/sanitizers",
    "sop2/l5",
    "sop2/l5_5",
    "sop2/l6",
    "sop2/l7",
    "sop2/l8",
    "sop2/netcat",
)
KINDS: frozenset[str] = frozenset(
    {"kind:definitional", "kind:howto", "kind:api", "kind:task", "kind:cross"}
)

GOLD = load_queries()


def test_gold_set_is_large_enough_and_has_unique_ids() -> None:
    assert len(GOLD) >= 40
    assert len({q.id for q in GOLD}) == len(GOLD)


def test_every_query_has_a_kind_a_course_and_a_target() -> None:
    for query in GOLD:
        assert KINDS & set(query.tags), query.id
        assert query.tag_value("course") in {"sop1", "sop2"}, query.id
        assert query.targets, query.id


def test_every_laboratory_has_at_least_three_queries() -> None:
    counts = Counter(lab for query in GOLD for lab in query.expected_lab_ids)
    thin = {lab: counts[lab] for lab in LABS if counts[lab] < 3}
    assert not thin, f"labs with fewer than three queries: {thin}"


def test_gold_set_covers_lectures_and_polish_students() -> None:
    assert sum(1 for q in GOLD if q.expected_document_ids) >= 5
    assert sum(1 for q in GOLD if "lang:pl" in q.tags) >= 3


def test_section_ids_are_document_scoped() -> None:
    for query in GOLD:
        for key in query.expected_section_ids:
            document_id, separator, section_id = key.partition("#")
            assert separator and document_id and section_id, f"{query.id}: {key}"


def test_filter_by_tag_requires_every_tag() -> None:
    polish = filter_by_tag(GOLD, ["lang:pl", "course:sop2"])
    assert polish and all("lang:pl" in q.tags and "course:sop2" in q.tags for q in polish)


def test_validate_queries_reports_unknown_ids() -> None:
    index = CorpusIndex(
        document_ids={"sop1/l1", "sop1/l1/summary"},
        lab_ids={"sop1/l1"},
        section_keys={"sop1/l1#browsing-a-directory"},
    )
    queries = [
        EvalQueryFile(
            id="good",
            query="q",
            expected_lab_ids=["sop1/l1"],
            expected_section_ids=["sop1/l1#browsing-a-directory"],
        ),
        EvalQueryFile(
            id="bad",
            query="q",
            expected_lab_ids=["sop1/l9"],
            expected_section_ids=["sop1/l1#nope"],
        ),
        EvalQueryFile(id="empty", query="q"),
    ]
    issues = validate_queries(queries, index)
    assert {(i.query_id, i.field) for i in issues} == {
        ("bad", "expected_lab_ids"),
        ("bad", "expected_section_ids"),
        ("empty", "targets"),
    }


def test_corpus_index_knows_documents_by_prefix() -> None:
    index = CorpusIndex(document_ids={"sop2/lecture/vmem/index"})
    assert index.knows_document("sop2/lecture/vmem")
    assert not index.knows_document("sop2/lecture/vme")


def test_load_queries_refuses_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "queries.yaml"
    path.write_text(
        "queries:\n"
        "  - {id: a, query: one, expected_lab_ids: [sop1/l1]}\n"
        "  - {id: a, query: two, expected_lab_ids: [sop1/l1]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate query id"):
        load_queries(path)


def test_corpus_index_falls_back_to_data_raw_when_the_database_is_down(
    settings: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rag_lab_generator.eval import queries as queries_module

    monkeypatch.setattr(
        queries_module, "_index_from_database", lambda _s: (_ for _ in ()).throw(RuntimeError("no"))
    )
    monkeypatch.setattr(queries_module, "_index_from_raw", lambda _s: CorpusIndex(source="stub"))
    assert corpus_index(settings).source == "stub"  # type: ignore[arg-type]
