"""
Role:   Gold query set: the model that extends EvalQuery, the yaml loader and the id validator.
Input:  eval/queries.yaml (or any path given on the CLI); documents and chunks of the corpus,
        read from Postgres or, when the database is unreachable, from data/raw.
Output: list[EvalQueryFile]; a CorpusIndex of known ids; ValidationIssue rows for unknown ids.
Flow:   load_queries() parses the yaml into EvalQueryFile models and refuses duplicate ids;
        corpus_index() collects document ids, lab ids and "<document>#<section>" keys from the
        chunks table, falling back to ingestion.load_documents(); validate_queries() reports every
        expected lab, document and section id that the index does not know.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from rag_lab_generator.config import Settings
from rag_lab_generator.models import EvalQuery, LabDocument
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

QUERIES_PATH = Path(__file__).resolve().parent / "queries.yaml"
SECTION_SEPARATOR = "#"


class EvalQueryFile(EvalQuery):
    """EvalQuery plus the document-level expectation the base model has no field for."""

    expected_document_ids: list[str] = Field(
        default_factory=list,
        description="document ids (or id prefixes) expected for queries without an owning lab",
    )

    @property
    def targets(self) -> list[str]:
        """Every document-level expectation: owning labs first, then explicit documents."""
        return [*self.expected_lab_ids, *self.expected_document_ids]

    def tag_value(self, prefix: str) -> str | None:
        for tag in self.tags:
            if tag.startswith(f"{prefix}:"):
                return tag.split(":", 1)[1]
        return None


class CorpusIndex(BaseModel):
    """Ids the gold set may refer to."""

    document_ids: set[str] = Field(default_factory=set)
    lab_ids: set[str] = Field(default_factory=set)
    section_keys: set[str] = Field(default_factory=set)
    source: str = "postgres"

    def knows_document(self, target: str) -> bool:
        return any(doc == target or doc.startswith(f"{target}/") for doc in self.document_ids)

    def knows_lab(self, lab_id: str) -> bool:
        return lab_id in self.lab_ids or self.knows_document(lab_id)

    def knows_section(self, key: str) -> bool:
        return key in self.section_keys


class ValidationIssue(BaseModel):
    """One unknown id found in the gold set."""

    query_id: str
    field: str
    value: str


def load_queries(path: Path = QUERIES_PATH) -> list[EvalQueryFile]:
    """Parse the yaml gold set and refuse duplicate query ids."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = raw["queries"] if isinstance(raw, dict) else raw
    queries = [EvalQueryFile(**entry) for entry in entries]
    seen: set[str] = set()
    for query in queries:
        if query.id in seen:
            raise ValueError(f"duplicate query id {query.id!r} in {path}")
        seen.add(query.id)
    return queries


def filter_by_tag(queries: Iterable[EvalQueryFile], tags: list[str]) -> list[EvalQueryFile]:
    """Keep the queries carrying every requested tag."""
    wanted = set(tags)
    return [q for q in queries if wanted <= set(q.tags)]


def corpus_index(settings: Settings) -> CorpusIndex:
    """Collect known ids from Postgres, falling back to data/raw when the database is down."""
    try:
        return _index_from_database(settings)
    except Exception:  # noqa: BLE001 - any database failure must degrade to the file corpus
        return _index_from_raw(settings)


def _index_from_database(settings: Settings) -> CorpusIndex:
    store = PostgresStore(settings)
    with store.connection() as conn:
        documents = conn.execute("SELECT id, lab_id FROM documents").fetchall()
        sections = conn.execute(
            "SELECT DISTINCT document_id, section_id FROM chunks WHERE section_id IS NOT NULL"
        ).fetchall()
    if not documents:
        raise RuntimeError("documents table is empty")
    index = CorpusIndex(source="postgres")
    for row in documents:
        index.document_ids.add(row["id"])
        if row["lab_id"]:
            index.lab_ids.add(row["lab_id"])
    for row in sections:
        index.section_keys.add(f"{row['document_id']}{SECTION_SEPARATOR}{row['section_id']}")
    return index


def _index_from_raw(settings: Settings) -> CorpusIndex:
    """Rebuild the index from data/raw so the gold set can be validated without a database."""
    from rag_lab_generator.ingestion.pipeline import load_documents

    index = CorpusIndex(source="data/raw")
    for document in load_documents(settings):
        index.document_ids.add(document.id)
        if document.lab_id:
            index.lab_ids.add(document.lab_id)
        if isinstance(document, LabDocument):
            index.lab_ids.add(document.id)
        for section in document.sections:
            index.section_keys.add(f"{document.id}{SECTION_SEPARATOR}{section.id}")
    return index


def validate_queries(queries: list[EvalQueryFile], index: CorpusIndex) -> list[ValidationIssue]:
    """Report every expected lab, document or section id the corpus does not contain."""
    issues: list[ValidationIssue] = []
    for query in queries:
        if not query.targets:
            issues.append(ValidationIssue(query_id=query.id, field="targets", value="<empty>"))
        for lab_id in query.expected_lab_ids:
            if not index.knows_lab(lab_id):
                issues.append(
                    ValidationIssue(query_id=query.id, field="expected_lab_ids", value=lab_id)
                )
        for document_id in query.expected_document_ids:
            if not index.knows_document(document_id):
                issues.append(
                    ValidationIssue(
                        query_id=query.id, field="expected_document_ids", value=document_id
                    )
                )
        for key in query.expected_section_ids:
            if not index.knows_section(key):
                issues.append(
                    ValidationIssue(query_id=query.id, field="expected_section_ids", value=key)
                )
    return issues
