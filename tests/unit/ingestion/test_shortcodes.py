"""
Role:   Unit tests of the hugo shortcode expander.
Input:  Inline markdown snippets and the demo.c fixture.
Output: Assertions on the expanded text and the recorded references.
Flow:   Checks hint/answer/details/katex unwrapping, includecode inlining, resource and ref
        resolution, and that fenced code blocks are never touched.
"""

from pathlib import Path

from rag_lab_generator.ingestion.parsers.shortcodes import expand_shortcodes, split_fences


def test_hint_keeps_inner_text_and_drops_wrapper() -> None:
    result = expand_shortcodes("{{< hint info >}}\nRead the man pages.\n{{< /hint >}}")
    assert "Read the man pages." in result.text
    assert "hint" not in result.text


def test_answer_and_details_are_recorded() -> None:
    text = (
        "{{< answer >}}\nBecause of closedir.\n{{</ answer >}}\n"
        '{{< details "Answer" >}} Yes. {{< /details >}}'
    )
    result = expand_shortcodes(text)
    assert result.answers == ["Because of closedir.", "Yes."]
    assert "**Answer:** Because of closedir." in result.text
    assert "{{" not in result.text


def test_includecode_inlines_the_file(fixtures_dir: Path) -> None:
    result = expand_shortcodes('{{< includecode "demo.c" >}}', base_dir=fixtures_dir)
    assert result.code_refs == ["demo.c"]
    assert "```c" in result.text
    assert "opendir" in result.text


def test_includecode_of_a_missing_file_is_reported(tmp_path: Path) -> None:
    result = expand_shortcodes('{{< includecode "nope.c" >}}', base_dir=tmp_path)
    assert result.unresolved == ["includecode nope.c"]
    assert "```c" in result.text


def test_resource_and_ref_are_resolved() -> None:
    text = '[demo]({{< resource demo.c >}}) and [t]({{< ref "/sop1/lab/l1/example1" >}})'
    result = expand_shortcodes(text, page_url_path="sop1/lab/l9")
    assert "[demo](demo.c)" in result.text
    assert "https://sop.mini.pw.edu.pl/en/sop1/lab/l1/example1/" in result.text
    assert result.resources == ["demo.c"]


def test_relative_ref_uses_the_page_path() -> None:
    result = expand_shortcodes('{{< ref "l7" >}}', page_url_path="sop2/lab")
    assert result.text == "https://sop.mini.pw.edu.pl/en/sop2/lab/l7/"


def test_katex_becomes_inline_math() -> None:
    assert expand_shortcodes("{{< katex >}}a+b{{< /katex >}}").text == "$a+b$"


def test_shortcodes_inside_fences_are_left_alone() -> None:
    text = "```c\n/* {{< hint info >}} */\n```\n{{< hint info >}}outside{{< /hint >}}"
    result = expand_shortcodes(text)
    assert "{{< hint info >}} */" in result.text
    assert "outside" in result.text


def test_split_fences_alternates_code_and_prose() -> None:
    parts = split_fences("a\n```\ncode\n```\nb")
    assert [is_code for is_code, _ in parts] == [False, True, False]
    assert parts[1][1].strip().startswith("```")
