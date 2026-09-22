"""
Role:   Unit tests for the LLM-as-judge: prompt assembly, answer parsing and the offline path.
Input:  Settings fixture (temporary data dir, fake llm) and hand-written judge answers.
Output: pytest assertions.
Flow:   Checks that the prompt carries the generated lab and the references, that a json answer
        becomes JudgeScores, that garbage is rejected, and that the offline provider yields the
        neutral placeholder scores together with the prompt.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.eval import judge


def test_build_prompt_contains_the_lab_and_the_references() -> None:
    prompt = judge.build_prompt("# My lab\n## Stages", ["### sop1/l3 / example1: threads"])
    assert "# My lab" in prompt
    assert "sop1/l3 / example1" in prompt
    assert "api_grounding" in prompt


def test_build_prompt_without_references_says_so() -> None:
    assert "(no reference task available)" in judge.build_prompt("# lab", [])


def test_parse_scores_reads_the_json_object() -> None:
    scores = judge.parse_scores(
        'here you go {"style_match": 5, "difficulty_match": 4, "api_grounding": 3,'
        ' "completeness": 2, "comment": "fine"} thanks'
    )
    assert scores is not None
    assert (scores.style_match, scores.completeness) == (5, 2)
    assert scores.overall == 3.5


def test_parse_scores_rejects_non_json_answers() -> None:
    assert judge.parse_scores("[fake-llm] nothing to see") is None
    assert judge.parse_scores("{not json at all}") is None


def test_judge_lab_with_the_offline_provider_returns_placeholder_scores(
    settings: Settings,
) -> None:
    result = judge.judge_lab(settings, "# Generated lab\n## Stages\n1. do something")
    assert result.parsed is False
    assert result.scores.overall == judge.NEUTRAL_SCORE
    assert "# Generated lab" in result.prompt
    assert result.model == "fake"


def test_judge_lab_parses_a_scripted_answer(settings: Settings) -> None:
    canned = '{"style_match": 4, "difficulty_match": 4, "api_grounding": 5, "completeness": 4}'
    llm = judge.create("llm", settings.llm_provider, settings=settings, canned=canned)
    response = llm.complete([])
    scores = judge.parse_scores(response.text)
    assert scores is not None and scores.api_grounding == 5
