"""
Role:   Unit tests for the prompt templates shipped with the generation layer.
Input:  The .md templates in generation/prompts and canned placeholder values.
Output: Assertions; no side effects.
Flow:   Checks that every template the tools and the summarizer use exists, that the system
        prompt states the grounding rules and that each template formats without leftover
        placeholders and keeps the structure the course tasks need.
"""

import pytest

from rag_lab_generator.generation.prompts import PROMPTS_DIR, load_prompt

PLACEHOLDERS = {
    "generate_lab": {
        "topic": "FIFO chat",
        "course": "sop1",
        "difficulty": "medium",
        "based_on": "sop1/l5_fifo",
        "context": "[sop1/l5_fifo / named-pipes]\nmkfifo() creates a named pipe.",
    },
    "explain_topic": {
        "topic": "signals",
        "course": "sop1",
        "depth": "short",
        "context": "[sop1/l3_signals / intro]\nsigaction() installs a handler.",
    },
    "visualize_concept": {
        "concept": "fork/exec/wait lifecycle",
        "diagram_type": "sequenceDiagram",
        "context": "[sop1/l4_processes / fork]\nfork() duplicates the process.",
    },
    "summarize_lab": {"outline": "L1 - Filesystem: opendir, readdir, stat"},
}


def test_all_templates_exist() -> None:
    names = {path.stem for path in PROMPTS_DIR.glob("*.md")}
    assert {"system_agent", *PLACEHOLDERS} <= names


def test_system_prompt_states_the_rules() -> None:
    system = load_prompt("system_agent")
    lowered = system.lower()
    assert "sop1" in lowered and "sop2" in lowered
    assert "language of the user" in lowered
    assert "never invent posix apis" in lowered


@pytest.mark.parametrize("name", sorted(PLACEHOLDERS))
def test_template_formats(name: str) -> None:
    rendered = load_prompt(name, **PLACEHOLDERS[name])
    for value in PLACEHOLDERS[name].values():
        assert value.splitlines()[-1] in rendered
    assert "{" not in rendered.replace("{{", "").replace("}}", "")


def test_generate_lab_demands_the_course_structure() -> None:
    rendered = load_prompt("generate_lab", **PLACEHOLDERS["generate_lab"])
    assert "## Description" in rendered
    assert "## Stages" in rendered
    assert "To show:" in rendered
