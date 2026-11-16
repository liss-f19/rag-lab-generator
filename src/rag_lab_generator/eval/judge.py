"""
Role:   LLM-as-judge for generated labs: scores one markdown task against reference lab tasks.
Input:  Settings, the generated markdown, reference task statements (read from data/raw lab.xml)
        and an llm name resolved through the registry.
Output: JudgeResult with the four 1-5 scores, the raw answer and the prompt used, for inspection.
Flow:   reference_tasks() reads the tasks of the reference labs; build_prompt() renders the rubric
        with the markdown and those tasks; judge_lab() sends it through the registry llm and
        parses the json answer, returning the neutral placeholder scores when the provider is the
        offline one and answers no json.
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from rag_lab_generator.config import Settings
from rag_lab_generator.models import LLMMessage
from rag_lab_generator.registry import create

CRITERIA: tuple[str, ...] = ("style_match", "difficulty_match", "api_grounding", "completeness")
NEUTRAL_SCORE = 3
MAX_REFERENCE_CHARS = 6000
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM = (
    "You grade laboratory assignments for a university Operating Systems course (POSIX, C). "
    "You answer with one json object and nothing else."
)

RUBRIC = """Score the generated laboratory task below against the reference tasks of the course.

Reference tasks (the style and difficulty to match):

---
{references}
---

Generated task:

---
{generated}
---

Score each criterion from 1 (bad) to 5 (indistinguishable from a real course task):

- style_match: same structure, tone and level of detail as the reference tasks (description,
  positional arguments, example run, numbered stages with a "To show:" line).
- difficulty_match: comparable amount of work and comparable API surface, neither trivial nor
  beyond the scope of the course.
- api_grounding: every POSIX function, macro and header mentioned exists and is used correctly;
  nothing invented and nothing outside the material of the referenced labs.
- completeness: the statement is self-contained: inputs, outputs, error handling and the stages
  are all specified well enough to implement and to grade.

Answer with exactly this json object:
{{"style_match": <1-5>, "difficulty_match": <1-5>, "api_grounding": <1-5>,
  "completeness": <1-5>, "comment": "<one sentence>"}}
"""


class JudgeScores(BaseModel):
    """The four rubric scores of one generated lab."""

    style_match: int = NEUTRAL_SCORE
    difficulty_match: int = NEUTRAL_SCORE
    api_grounding: int = NEUTRAL_SCORE
    completeness: int = NEUTRAL_SCORE
    comment: str = ""

    @property
    def overall(self) -> float:
        return sum(int(getattr(self, name)) for name in CRITERIA) / len(CRITERIA)


class JudgeResult(BaseModel):
    """Scores plus everything needed to audit how they were produced."""

    scores: JudgeScores
    model: str
    prompt: str
    raw_answer: str = ""
    parsed: bool = Field(default=False, description="false when the placeholder scores are used")


def reference_tasks(settings: Settings, lab_ids: list[str]) -> list[str]:
    """Read the example tasks of the given labs from data/raw as 'lab/task: statement' blocks."""
    from rag_lab_generator.ingestion.lab_xml import read_lab_xml

    blocks: list[str] = []
    for path in sorted(Path(settings.raw_dir).glob("*/*/lab.xml")):
        lab = read_lab_xml(path, load_code=False)
        if lab_ids and lab.id not in lab_ids:
            continue
        for task in lab.tasks:
            stages = "\n".join(f"{stage.n}. {stage.text}" for stage in task.stages)
            blocks.append(f"### {lab.id} / {task.id}: {task.title}\n{task.statement}\n{stages}")
    return blocks


def build_prompt(generated: str, references: list[str]) -> str:
    """Render the rubric, truncating the reference block so the prompt stays affordable."""
    joined = "\n\n".join(references)[:MAX_REFERENCE_CHARS] or "(no reference task available)"
    return RUBRIC.format(references=joined, generated=generated)


def parse_scores(answer: str) -> JudgeScores | None:
    """Read the json object out of the answer; None when the provider returned no json."""
    match = _JSON_RE.search(answer)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return JudgeScores(**{key: payload[key] for key in payload if key in {*CRITERIA, "comment"}})


def judge_lab(
    settings: Settings,
    generated: str,
    lab_ids: list[str] | None = None,
    llm_name: str | None = None,
) -> JudgeResult:
    """Score one generated lab; requires ANTHROPIC_API_KEY for real scores."""
    prompt = build_prompt(generated, reference_tasks(settings, lab_ids or []))
    llm = create("llm", llm_name or settings.llm_provider, settings=settings)
    response = llm.complete([LLMMessage(role="user", content=prompt)], system=SYSTEM)
    scores = parse_scores(response.text)
    return JudgeResult(
        scores=scores or JudgeScores(comment="placeholder scores: the provider returned no json"),
        model=response.model,
        prompt=prompt,
        raw_answer=response.text,
        parsed=scores is not None,
    )
