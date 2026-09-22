"""
Role:   Unit tests of the hugo markdown parser (sections, tasks, topics, urls).
Input:  The example task and tutorial fixture pages.
Output: Assertions on Section, Task and topic extraction.
Flow:   Splits a body that contains a heading-like line inside a fence, parses the fixture task
        and checks the derived ids, stages, attachments and public URLs.
"""

from pathlib import Path

from rag_lab_generator.ingestion.parsers.hugo_markdown import (
    extract_topics,
    lab_number,
    page_url,
    parse_task,
    slugify,
    split_sections,
)

BODY_WITH_FENCE = """# Title

intro text

## First

```c
## this is not a heading
int main(void) { return 0; }
```

### Nested

tail
"""


def test_split_sections_keeps_fenced_headings_inside_their_section() -> None:
    sections = split_sections(BODY_WITH_FENCE)
    assert [s.title for s in sections] == ["Title", "First", "Nested"]
    assert "## this is not a heading" in sections[1].text
    assert sections[2].parent_id == "first"
    assert sections[1].parent_id == "title"
    assert [s.order for s in sections] == [0, 1, 2]


def test_split_sections_creates_an_overview_for_a_body_without_headings() -> None:
    sections = split_sections("just text")
    assert len(sections) == 1
    assert sections[0].id == "overview"


def test_duplicate_headings_get_unique_ids() -> None:
    sections = split_sections("## Task\n\na\n\n## Task\n\nb\n")
    assert [s.id for s in sections] == ["task", "task-2"]


def test_parse_task_reads_statement_stages_and_attachments(example_task_page: Path) -> None:
    task = parse_task(example_task_page, example_task_page.parent)
    assert task.id == "example_task"
    assert task.title == "Example task 1 on fixtures"
    assert len(task.stages) == 3
    assert task.stages[0].n == 1
    assert "Open the directory" in task.stages[0].text
    assert "Write a program" in task.statement
    assert "Starting code" in task.statement
    assert task.attachments == ["src/fixture.zip"]
    assert task.source_url.endswith("/en/example_task/")


def test_extract_topics_picks_api_names_and_macros() -> None:
    text = (
        "Use `opendir` and `readdir` (`man 3p fdopendir`).\n\n"
        "```c\nDIR *opendir(const char *p);\nint readdir(void);\n```\n"
        "`S_ISDIR` is a macro but `the` is not."
    )
    topics = extract_topics(text)
    assert topics[:2] == ["opendir", "readdir"]
    assert "S_ISDIR" in topics
    assert "fdopendir" in topics
    assert "the" not in topics


def test_lab_number_and_slugify() -> None:
    assert lab_number("l5_5") == "5.5"
    assert lab_number("l1") == "1"
    assert lab_number("netcat") == "netcat"
    assert slugify("Browsing a Directory!") == "browsing-a-directory"


def test_page_url_drops_the_index_file_name() -> None:
    assert (
        page_url(Path("sop1/lab/l1/_index.en.md")) == "https://sop.mini.pw.edu.pl/en/sop1/lab/l1/"
    )
    assert (
        page_url(Path("sop2/lab/netcat.en.md")) == "https://sop.mini.pw.edu.pl/en/sop2/lab/netcat/"
    )
