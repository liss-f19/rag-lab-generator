"""
Role:   Shared Postgres access: connection factory, schema application, document and chunk upserts.
Input:  Settings.database_url; Document / Chunk models to persist.
Output: Persisted rows; Chunk models read back by id.
Flow:   connection() opens a psycopg connection with pgvector adapters registered;
        apply_schema() executes sql/001_schema.sql; upsert_* write rows idempotently;
        fetch_chunks() rebuilds Chunk models. Vector and graph tables are used by
        vector_store.py and graph_store.py on top of this class.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    Course,
    Document,
    DocumentHeader,
    DocumentKind,
)

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "sql" / "001_schema.sql"


class PostgresStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(self.settings.database_url, row_factory=dict_row) as conn:
            register_vector(conn)
            yield conn

    def apply_schema(self, path: Path = SCHEMA_PATH) -> None:
        with self.connection() as conn:
            conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()

    # ------------------------------------------------------------ documents

    def upsert_documents(self, docs: list[Document]) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO documents (id, course, kind, lab_id, title, source_url, lang, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    course = EXCLUDED.course, kind = EXCLUDED.kind, lab_id = EXCLUDED.lab_id,
                    title = EXCLUDED.title, source_url = EXCLUDED.source_url,
                    lang = EXCLUDED.lang, metadata = EXCLUDED.metadata
                """,
                [
                    (
                        d.id,
                        d.course.value,
                        d.kind.value,
                        d.lab_id,
                        d.title,
                        d.source_url,
                        d.lang,
                        json.dumps(d.metadata, default=str),
                    )
                    for d in docs
                ],
            )
            conn.commit()

    # ------------------------------------------------------------ chunks

    def delete_chunks(self, strategy: str) -> int:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM chunks WHERE strategy = %s", (strategy,))
            conn.commit()
            return cur.rowcount

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (id, document_id, lab_id, course, kind, strategy, idx,
                                    parent_id, section_id, text, char_count, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text, char_count = EXCLUDED.char_count,
                    parent_id = EXCLUDED.parent_id, section_id = EXCLUDED.section_id,
                    kind = EXCLUDED.kind, lab_id = EXCLUDED.lab_id, metadata = EXCLUDED.metadata
                """,
                [
                    (
                        c.id,
                        c.document_id,
                        c.lab_id,
                        c.course.value,
                        c.kind.value,
                        c.strategy,
                        c.idx,
                        c.parent_id,
                        c.section_id,
                        c.text,
                        c.char_count,
                        json.dumps(c.metadata, default=str),
                    )
                    for c in chunks
                ],
            )
            conn.commit()

    def fetch_document_headers(self, ids: list[str]) -> dict[str, DocumentHeader]:
        """Title, kind and metadata of the given documents, without their sections."""
        if not ids:
            return {}
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, course, kind, lab_id, title, metadata FROM documents"
                " WHERE id = ANY(%s)",
                (ids,),
            ).fetchall()
        headers: dict[str, DocumentHeader] = {}
        for row in rows:
            metadata = row["metadata"]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            headers[row["id"]] = DocumentHeader(
                id=row["id"],
                course=Course(row["course"]),
                kind=DocumentKind(row["kind"]),
                lab_id=row["lab_id"],
                title=row["title"],
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        return headers

    def fetch_chunks(self, ids: list[str]) -> dict[str, Chunk]:
        if not ids:
            return {}
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM chunks WHERE id = ANY(%s)", (ids,)).fetchall()
        return {row["id"]: self.row_to_chunk(row) for row in rows}

    def list_chunks(self, strategy: str, lab_id: str | None = None) -> list[Chunk]:
        query = "SELECT * FROM chunks WHERE strategy = %s"
        params: list[Any] = [strategy]
        if lab_id is not None:
            query += " AND lab_id = %s"
            params.append(lab_id)
        query += " ORDER BY document_id, idx"
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self.row_to_chunk(r) for r in rows]

    @staticmethod
    def row_to_chunk(row: dict[str, Any]) -> Chunk:
        metadata = row["metadata"]
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            course=Course(row["course"]),
            lab_id=row["lab_id"],
            kind=ChunkKind(row["kind"]),
            strategy=row["strategy"],
            idx=row["idx"],
            text=row["text"],
            char_count=row["char_count"],
            parent_id=row["parent_id"],
            section_id=row["section_id"],
            metadata=metadata if isinstance(metadata, dict) else json.loads(metadata),
        )
