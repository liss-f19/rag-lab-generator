"""
Role:   Writer of summary.md and summary.pdf for one laboratory.
Input:  A LabDocument, the target lab directory and an LLM created through the registry.
Output: summary.md (deterministic outline plus the model answer) and summary.pdf next to it.
Flow:   build_outline renders the lab structure as markdown, build_prompt turns it into an
        instruction for the model, summarize_lab concatenates both into summary.md and
        render_pdf converts that file through markdown -> html -> xhtml2pdf.
"""

import logging
from pathlib import Path

from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.models import LabDocument, LLMMessage

SNIPPET_CHARS = 300
SYSTEM_PROMPT = (
    "You write concise teaching summaries of Operating Systems laboratory materials "
    "for the SOP1/SOP2 courses at Warsaw University of Technology. Answer in English."
)
PDF_CSS = """
@page { size: a4 portrait; margin: 2cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.35; }
h1 { font-size: 16pt; } h2 { font-size: 13pt; } h3 { font-size: 11pt; }
code, pre { font-family: Courier, monospace; font-size: 8.5pt; background-color: #f2f2f2; }
"""


def build_outline(lab: LabDocument) -> str:
    """Render the deterministic outline of a lab: topics, tutorial sections and tasks."""
    lines: list[str] = [f"# {lab.course.value.upper()} lab {lab.number} - {lab.title}", ""]
    if lab.source_url:
        lines += [f"Source: {lab.source_url}", ""]
    lines += [f"- Lab id: `{lab.id}`", f"- Tutorial sections: {len(lab.sections)}"]
    lines += [f"- Tasks: {len(lab.tasks)}", f"- Source files: {len(lab.code_files)}", ""]
    if lab.topics:
        lines += ["## Topics", "", ", ".join(f"`{topic}`" for topic in lab.topics), ""]

    lines += ["## Tutorial outline", ""]
    for section in lab.sections:
        snippet = " ".join(section.text.split())[:SNIPPET_CHARS]
        lines.append(f"{'  ' * max(section.level - 1, 0)}- **{section.title}** - {snippet}")
    lines.append("")

    if lab.tasks:
        lines += ["## Tasks", ""]
        for task in lab.tasks:
            lines.append(f"- **{task.id}: {task.title}** - {len(task.stages)} stages")
            for stage in task.stages:
                lines.append(f"  {stage.n}. {' '.join(stage.text.split())[:SNIPPET_CHARS]}")
        lines.append("")

    if lab.code_files:
        lines += ["## Source files", ""]
        lines += [f"- `{file.ref}` ({file.lang})" for file in lab.code_files]
        lines.append("")
    return "\n".join(lines)


def build_prompt(lab: LabDocument) -> str:
    """Build the user prompt asking the model to summarize one lab from its outline."""
    return (
        "Summarize the following Operating Systems laboratory for a course knowledge base.\n"
        "Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, "
        "how the tasks are structured and what a student must already know.\n\n"
        f"{build_outline(lab)}"
    )


def summarize_lab(lab: LabDocument, llm: LLM, lab_dir: Path) -> Path:
    """Write summary.md for one lab; the outline is always included, the model text on top."""
    response = llm.complete([LLMMessage(role="user", content=build_prompt(lab))], SYSTEM_PROMPT)
    body = (
        f"# Summary: {lab.course.value.upper()} lab {lab.number} - {lab.title}\n\n"
        f"{response.text.strip()}\n\n---\n\n{build_outline(lab)}"
    )
    lab_dir.mkdir(parents=True, exist_ok=True)
    target = lab_dir / "summary.md"
    target.write_text(body, encoding="utf-8")
    return target


def render_pdf(markdown_path: Path, pdf_path: Path | None = None) -> Path:
    """Render a markdown file to pdf through markdown -> html -> xhtml2pdf."""
    # The renderer logs one warning per glyph missing from its core fonts; they are not actionable.
    for name in ("xhtml2pdf", "reportlab", "PIL"):
        logging.getLogger(name).setLevel(logging.ERROR)
    pdf_path = pdf_path or markdown_path.with_suffix(".pdf")
    import markdown as markdown_lib  # optional `ingest` extra

    html_body = markdown_lib.markdown(
        markdown_path.read_text(encoding="utf-8"), extensions=["fenced_code", "tables"]
    )
    document = (
        f"<html><head><meta charset='utf-8'><style>{PDF_CSS}</style></head>"
        f"<body>{html_body}</body></html>"
    )
    with pdf_path.open("wb") as handle:
        from xhtml2pdf import pisa  # optional `ingest` extra

        pisa.CreatePDF(src=document, dest=handle, encoding="utf-8")
    return pdf_path
