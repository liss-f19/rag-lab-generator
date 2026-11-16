"""
Role:   Conversion between LLM output (structured or markdown) and the GeneratedLab model.
Input:  LabDraft instances from structured output, or raw markdown produced by any provider.
Output: GeneratedLab models and their markdown rendering used by the agent tools.
Flow:   LabDraft mirrors the fields a model is asked to fill; draft_to_lab() attaches the
        course and reference labs; parse_lab_markdown() is a lenient fallback that reads the
        title, the "## Description" body and the numbered "## Stages" list; render_lab()
        writes the same shape back as markdown.
"""

import re
from typing import Literal, cast

from pydantic import BaseModel, Field

from rag_lab_generator.models import Course, GeneratedLab, Stage

_HEADING = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
_TITLE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*(?P<n>\d+)[.)]\s+(?P<text>.*)$")
_BULLET = re.compile(r"^\s*[-*]\s+(?P<text>.*)$")
_BACKTICKED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{2,})(?:\(\))?`")

Difficulty = Literal["easy", "medium", "hard"]


class LabDraft(BaseModel):
    """Structured output schema the LLM fills when the provider supports parsing."""

    title: str = Field(description="short lab title, e.g. 'L7 - FIFO based chat'")
    topics: list[str] = Field(default_factory=list, description="POSIX APIs and concepts used")
    description: str = Field(description="the '## Description' body including the example run")
    stages: list[str] = Field(
        default_factory=list,
        description="4-6 stages, each ending with 'To show: ...'",
    )
    hints: list[str] = Field(default_factory=list, description="optional notes for the student")
    difficulty: str = Field(default="medium", description="easy, medium or hard")


def draft_to_lab(
    draft: LabDraft,
    course: Course,
    based_on: list[str],
    difficulty: str | None = None,
) -> GeneratedLab:
    """Attach course context to a structured draft and normalise its stages."""
    level = _difficulty(difficulty or draft.difficulty)
    return GeneratedLab(
        title=draft.title.strip() or "Generated lab",
        course=course,
        based_on=based_on,
        topics=[t.strip() for t in draft.topics if t.strip()],
        description=draft.description.strip(),
        stages=[Stage(n=i, text=text.strip()) for i, text in enumerate(draft.stages, start=1)],
        hints=[h.strip() for h in draft.hints if h.strip()],
        difficulty=level,
    )


def parse_lab_markdown(
    text: str,
    course: Course,
    based_on: list[str] | None = None,
    difficulty: str | None = None,
    fallback_title: str = "Generated lab",
) -> GeneratedLab:
    """Read a markdown lab written in the course style; missing sections degrade gracefully."""
    sections = _split_sections(text)
    description = _first_section(sections, ("description", "opis", "task", "zadanie"))
    stages_body = _first_section(sections, ("stages", "etapy", "steps"))
    hints_body = _first_section(sections, ("hints", "notes", "remarks"))
    if not description:
        description = _body_before_headings(text)
    return GeneratedLab(
        title=_title(text, fallback_title),
        course=course,
        based_on=list(based_on or []),
        topics=_topics(description),
        description=description.strip(),
        stages=_stages(stages_body),
        hints=[m.group("text").strip() for m in _iter_matches(_BULLET, hints_body)],
        difficulty=_difficulty(difficulty),
    )


def render_lab(lab: GeneratedLab) -> str:
    """Render GeneratedLab back into the markdown layout of the course example tasks."""
    lines = [f"# {lab.title}", ""]
    meta = [f"course: {lab.course.value}", f"difficulty: {lab.difficulty}"]
    if lab.based_on:
        meta.append(f"based on: {', '.join(lab.based_on)}")
    if lab.topics:
        meta.append(f"topics: {', '.join(lab.topics)}")
    lines += ["*" + " | ".join(meta) + "*", "", "## Description", "", lab.description.strip(), ""]
    if lab.stages:
        lines += ["## Stages", ""]
        lines += [f"{stage.n}. {stage.text.strip()}" for stage in lab.stages]
        lines.append("")
    if lab.hints:
        lines += ["## Hints", ""]
        lines += [f"- {hint.strip()}" for hint in lab.hints]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_HEADING.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        key = match.group("title").strip().lower()
        sections.setdefault(key, text[match.end() : end].strip())
    return sections


def _first_section(sections: dict[str, str], names: tuple[str, ...]) -> str:
    for key, body in sections.items():
        if any(key.startswith(name) for name in names):
            return body
    return ""


def _body_before_headings(text: str) -> str:
    match = _HEADING.search(text)
    body = text[: match.start()] if match else text
    return _TITLE.sub("", body).strip()


def _title(text: str, fallback: str) -> str:
    match = _TITLE.search(text)
    if match:
        return match.group("title").strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip().lstrip("#").strip()
    return fallback


def _stages(body: str) -> list[Stage]:
    # keep continuation lines with the stage they belong to
    stages: list[Stage] = []
    current: list[str] = []
    for line in body.splitlines():
        match = _NUMBERED.match(line)
        if match:
            _flush(stages, current)
            current = [match.group("text").strip()]
        elif current and line.strip():
            current.append(line.strip())
    _flush(stages, current)
    return stages


def _flush(stages: list[Stage], current: list[str]) -> None:
    if current:
        stages.append(Stage(n=len(stages) + 1, text=" ".join(current).strip()))


def _topics(description: str) -> list[str]:
    seen: list[str] = []
    for match in _BACKTICKED.finditer(description):
        token = match.group(1)
        if token not in seen:
            seen.append(token)
    return seen[:12]


def _iter_matches(pattern: re.Pattern[str], body: str) -> list[re.Match[str]]:
    return [m for m in (pattern.match(line) for line in body.splitlines()) if m is not None]


def _difficulty(value: str | None) -> Difficulty:
    if value in ("easy", "medium", "hard"):
        return cast(Difficulty, value)
    return "medium"
