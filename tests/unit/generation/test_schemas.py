"""
Role:   Unit tests for the GeneratedLab parser and renderer.
Input:  A markdown lab written in the style of the course example tasks; a LabDraft instance.
Output: Assertions; no side effects.
Flow:   Parses the markdown, checks title, description, stages and hints, renders it back and
        parses it again to prove the round trip, then checks the degraded and structured paths.
"""

from rag_lab_generator.generation.schemas import (
    LabDraft,
    draft_to_lab,
    parse_lab_markdown,
    render_lab,
)
from rag_lab_generator.models import Course

MARKDOWN = """# L7 - FIFO based chat

## Description

Write a program that accepts the following positional parameters:

  - path
    path to the named pipe

The program creates the pipe with `mkfifo` and reads messages until EOF.

```
$ ./prog /tmp/chat
waiting
```

## Stages

1. Program creates the FIFO and exits. *To show:* run `./prog /tmp/chat` and `ls -l /tmp/chat`
2. Program opens the FIFO for reading
   and prints every line. *To show:* run it and write with `echo > /tmp/chat`
3. Program handles `SIGINT` and removes the pipe. *To show:* press Ctrl-C
4. Program forks a writer child. *To show:* run with two terminals

## Hints

- Check every return value and use `errno`
- Remember to `unlink` the pipe
"""


def test_parse_markdown_reads_every_section() -> None:
    lab = parse_lab_markdown(MARKDOWN, course=Course.SOP1, based_on=["sop1/l5_fifo"])
    assert lab.title == "L7 - FIFO based chat"
    assert lab.course is Course.SOP1
    assert lab.based_on == ["sop1/l5_fifo"]
    assert "named pipe" in lab.description
    assert [stage.n for stage in lab.stages] == [1, 2, 3, 4]
    assert "To show:" in lab.stages[0].text
    assert "and prints every line" in lab.stages[1].text
    assert lab.hints == [
        "Check every return value and use `errno`",
        "Remember to `unlink` the pipe",
    ]
    assert "mkfifo" in lab.topics


def test_render_round_trip() -> None:
    lab = parse_lab_markdown(MARKDOWN, course=Course.SOP1, based_on=["sop1/l5_fifo"])
    again = parse_lab_markdown(render_lab(lab), course=Course.SOP1, based_on=lab.based_on)
    assert again.title == lab.title
    assert [s.text for s in again.stages] == [s.text for s in lab.stages]
    assert again.hints == lab.hints


def test_render_contains_the_course_headings() -> None:
    lab = parse_lab_markdown(MARKDOWN, course=Course.SOP2)
    rendered = render_lab(lab)
    assert rendered.startswith("# L7 - FIFO based chat")
    assert "## Description" in rendered and "## Stages" in rendered
    assert "1. Program creates the FIFO" in rendered


def test_parse_degrades_without_headings() -> None:
    lab = parse_lab_markdown("[fake-llm] nothing useful", course=Course.SOP1)
    assert lab.title == "[fake-llm] nothing useful"
    assert lab.description == "[fake-llm] nothing useful"
    assert lab.stages == []
    assert lab.difficulty == "medium"


def test_draft_to_lab_numbers_stages() -> None:
    draft = LabDraft(
        title="L9 - epoll server",
        topics=["epoll_wait"],
        description="Write a server.",
        stages=["open a socket. To show: run it", "add epoll. To show: connect twice"],
        hints=["close descriptors"],
        difficulty="nonsense",
    )
    lab = draft_to_lab(draft, Course.SOP2, ["sop2/l3_sockets"])
    assert [stage.n for stage in lab.stages] == [1, 2]
    assert lab.difficulty == "medium"
    assert lab.course is Course.SOP2
