"""
Role:   Canonical XML form of a LabDocument: writer, reader and schema validation.
Input:  LabDocument to write, or a lab.xml path to read back (plus its src/ directory).
Output: lab.xml validated against docs/lab.xsd; LabDocument rebuilt from such a file.
Flow:   write_lab_xml builds the tree with lxml, puts every markdown body into CDATA, validates
        it and writes it; read_lab_xml parses the file, validates it again and rebuilds the
        model, optionally loading the code file contents from the sibling src/ directory.
"""

from functools import lru_cache
from pathlib import Path

from lxml import etree

from rag_lab_generator.models import (
    CodeFile,
    Course,
    LabDocument,
    Reference,
    Section,
    Stage,
    Task,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "lab.xsd"


class LabXmlError(ValueError):
    """Raised when a lab.xml document does not satisfy docs/lab.xsd."""


@lru_cache(maxsize=1)
def schema() -> etree.XMLSchema:
    """Load and cache the compiled lab.xsd schema."""
    return etree.XMLSchema(etree.parse(str(SCHEMA_PATH)))


def _cdata(parent: etree._Element, tag: str, text: str) -> etree._Element:
    child = etree.SubElement(parent, tag)
    child.text = etree.CDATA(text)
    return child


def build_tree(lab: LabDocument) -> etree._Element:
    """Build the lxml tree of one lab without touching the filesystem."""
    root = etree.Element("lab")
    root.set("id", lab.id)
    root.set("course", lab.course.value)
    root.set("number", lab.number)
    root.set("slug", lab.slug)
    root.set("lang", lab.lang)
    if lab.source_url:
        root.set("source_url", lab.source_url)

    etree.SubElement(root, "title").text = lab.title
    topics = etree.SubElement(root, "topics")
    for topic in lab.topics:
        etree.SubElement(topics, "topic").text = topic

    tutorial = etree.SubElement(root, "tutorial")
    for section in lab.sections:
        node = etree.SubElement(tutorial, "section")
        node.set("id", section.id)
        node.set("title", section.title)
        node.set("level", str(section.level))
        node.set("order", str(section.order))
        node.set("parent", section.parent_id or "")
        _cdata(node, "text", section.text)
        for ref in section.code_refs:
            code = etree.SubElement(node, "code")
            code.set("ref", ref)
            code.set("lang", Path(ref).suffix.lstrip(".") or "text")

    tasks = etree.SubElement(root, "tasks")
    for task in lab.tasks:
        node = etree.SubElement(tasks, "task")
        node.set("id", task.id)
        node.set("title", task.title)
        if task.source_url:
            node.set("source_url", task.source_url)
        _cdata(node, "statement", task.statement)
        stages = etree.SubElement(node, "stages")
        for stage in task.stages:
            item = etree.SubElement(stages, "stage")
            item.set("n", str(stage.n))
            item.text = etree.CDATA(stage.text)
        for ref in task.solution_refs:
            etree.SubElement(node, "solution").set("ref", ref)
        attachments = etree.SubElement(node, "attachments")
        for ref in task.attachments:
            etree.SubElement(attachments, "file").set("ref", ref)
        _cdata(node, "notes", task.notes)

    sources = etree.SubElement(root, "sources")
    for code_file in lab.code_files:
        node = etree.SubElement(sources, "file")
        node.set("ref", code_file.ref)
        node.set("lang", code_file.lang)
        if code_file.source_url:
            node.set("source_url", code_file.source_url)

    references = etree.SubElement(root, "references")
    for reference in lab.references:
        node = etree.SubElement(references, "ref")
        node.set("url", reference.url)
        node.set("title", reference.title)

    metadata = etree.SubElement(root, "metadata")
    for key, value in sorted(lab.metadata.items()):
        item = etree.SubElement(metadata, "item")
        item.set("key", key)
        item.text = str(value)

    return root


def validate(root: etree._Element) -> None:
    """Raise LabXmlError when the tree does not validate against docs/lab.xsd."""
    if not schema().validate(root):
        raise LabXmlError(f"lab.xml does not validate: {schema().error_log}")


def write_lab_xml(lab: LabDocument, path: Path) -> Path:
    """Serialize a LabDocument to path after validating it against the schema."""
    root = build_tree(lab)
    validate(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = etree.ElementTree(root)
    etree.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True, pretty_print=True)
    return path


def _text_of(node: etree._Element | None) -> str:
    return "" if node is None or node.text is None else str(node.text)


def read_lab_xml(path: Path, load_code: bool = True) -> LabDocument:
    """Rebuild a LabDocument from lab.xml, loading src/ file contents when they exist."""
    root = etree.parse(str(path)).getroot()
    validate(root)
    lab_dir = path.parent

    sections = [
        Section(
            id=str(node.get("id")),
            title=str(node.get("title")),
            level=int(str(node.get("level"))),
            order=int(str(node.get("order"))),
            text=_text_of(node.find("text")),
            code_refs=[str(code.get("ref")) for code in node.findall("code")],
            parent_id=node.get("parent") or None,
        )
        for node in root.findall("tutorial/section")
    ]
    tasks = [
        Task(
            id=str(node.get("id")),
            title=str(node.get("title")),
            statement=_text_of(node.find("statement")),
            stages=[
                Stage(n=int(str(stage.get("n"))), text=_text_of(stage))
                for stage in node.findall("stages/stage")
            ],
            solution_refs=[str(item.get("ref")) for item in node.findall("solution")],
            attachments=[str(item.get("ref")) for item in node.findall("attachments/file")],
            notes=_text_of(node.find("notes")),
            source_url=node.get("source_url"),
        )
        for node in root.findall("tasks/task")
    ]
    code_files: list[CodeFile] = []
    for node in root.findall("sources/file"):
        ref = str(node.get("ref"))
        target = lab_dir / ref
        content = ""
        if load_code and target.is_file() and target.suffix.lower() not in {".zip", ".pdf"}:
            content = target.read_text(encoding="utf-8", errors="replace")
        code_files.append(
            CodeFile(
                ref=ref,
                lang=str(node.get("lang") or "text"),
                content=content,
                source_url=node.get("source_url"),
            )
        )

    return LabDocument(
        id=str(root.get("id")),
        course=Course(str(root.get("course"))),
        title=_text_of(root.find("title")),
        lang=str(root.get("lang") or "en"),
        number=str(root.get("number")),
        slug=str(root.get("slug")),
        source_url=root.get("source_url"),
        sections=sections,
        topics=[_text_of(node) for node in root.findall("topics/topic")],
        tasks=tasks,
        code_files=code_files,
        references=[
            Reference(url=str(node.get("url")), title=str(node.get("title") or ""))
            for node in root.findall("references/ref")
        ],
        metadata={str(node.get("key")): _text_of(node) for node in root.findall("metadata/item")},
    )
