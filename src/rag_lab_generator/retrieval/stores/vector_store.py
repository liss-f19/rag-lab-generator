"""
Role:   Postgres access for the vector and full-text side of retrieval.
Input:  Settings.database_url; embeddings to persist; queries plus SearchFilters at search time.
Output: Persisted embedding rows; ranked (chunk_id, score) lists; corpus counters for the CLI.
Flow:   Extends PostgresStore with upsert/delete of embedder-scoped vectors, cosine dense search
        over `1 - (embedding <=> query)`, full-text search over the generated tsvector column
        whose terms are OR-ed and ranked with ts_rank_cd (plain or idf-weighted), and count
        helpers for `rag-lab db-stats`; document frequencies are cached on the instance.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import psycopg
from numpy.typing import NDArray

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk
from rag_lab_generator.retrieval.stores.postgres import PostgresStore

# quoted to keep the store importable before the searchers package that owns SearchFilters
if TYPE_CHECKING:
    from rag_lab_generator.retrieval.searchers.base import SearchFilters

Vector = list[float] | NDArray[Any]
COUNTED_TABLES: tuple[str, ...] = ("documents", "chunks", "embeddings", "nodes", "edges")
TSQUERY_PARSERS: tuple[str, ...] = ("websearch_to_tsquery", "plainto_tsquery")
RANK_NORMALIZATION = 32  # ts_rank_cd flag: score / (score + 1), keeps ranks comparable


class VectorStore(PostgresStore):
    """Chunk store extended with embedding storage, dense search and lexical search."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._df_cache: dict[tuple[str, str], int] = {}
        self._chunk_count_cache: dict[str, int] = {}

    # ------------------------------------------------------------ embeddings

    def upsert_embeddings(
        self, embedder_name: str, chunk_ids: Sequence[str], vectors: Sequence[Vector]
    ) -> None:
        if not chunk_ids:
            return
        if len(chunk_ids) != len(vectors):
            raise ValueError("chunk_ids and vectors must have the same length")
        rows = [
            (chunk_id, embedder_name, int(vector.shape[0]), vector)
            for chunk_id, vector in zip(chunk_ids, [_as_vector(v) for v in vectors], strict=True)
        ]
        with self.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO embeddings (chunk_id, embedder, dim, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id, embedder) DO UPDATE SET
                    dim = EXCLUDED.dim, embedding = EXCLUDED.embedding
                """,
                rows,
            )
            conn.commit()

    def delete_embeddings(self, embedder_name: str) -> int:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM embeddings WHERE embedder = %s", (embedder_name,))
            conn.commit()
            return cur.rowcount

    def chunks_without_embeddings(self, embedder_name: str, strategy: str) -> list[Chunk]:
        """List chunks of one strategy that have no vector for this embedder yet."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.* FROM chunks c
                LEFT JOIN embeddings e ON e.chunk_id = c.id AND e.embedder = %s
                WHERE c.strategy = %s AND e.chunk_id IS NULL
                ORDER BY c.document_id, c.idx
                """,
                (embedder_name, strategy),
            ).fetchall()
        return [self.row_to_chunk(row) for row in rows]

    # ------------------------------------------------------------ search

    def dense_search(
        self, query_vec: Vector, embedder_name: str, k: int, filters: "SearchFilters"
    ) -> list[tuple[str, float]]:
        """Rank chunks by cosine similarity against the stored vectors of one embedder."""
        vector = _as_vector(query_vec)
        clauses, params = _filter_sql(filters, "c")
        sql = f"""
            SELECT c.id AS id, 1 - (e.embedding <=> %s::vector) AS score
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            WHERE e.embedder = %s AND {" AND ".join(clauses)}
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """
        args: list[Any] = [vector, embedder_name, *params, vector, k]
        with self.connection() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [(row["id"], float(row["score"])) for row in rows]

    def lexical_search(
        self, query: str, k: int, filters: "SearchFilters"
    ) -> list[tuple[str, float]]:
        """Rank chunks matching any query term, best coverage first; empty for a term-less query."""
        tsquery = self.or_tsquery(query)
        if not tsquery:
            return []
        clauses, params = _filter_sql(filters, "c")
        sql = f"""
            SELECT c.id AS id, ts_rank_cd(c.tsv, %s::tsquery, {RANK_NORMALIZATION}) AS score
            FROM chunks c
            WHERE c.tsv @@ %s::tsquery AND {" AND ".join(clauses)}
            ORDER BY score DESC, c.id
            LIMIT %s
        """
        args: list[Any] = [tsquery, tsquery, *params, k]
        with self.connection() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [(row["id"], float(row["score"])) for row in rows]

    def lexical_search_idf(
        self, query: str, k: int, filters: "SearchFilters"
    ) -> list[tuple[str, float]]:
        """Rank chunks by the idf-weighted sum of the per-term ts_rank_cd scores."""
        lexemes = self.query_lexemes(query)
        total = self.chunk_count(filters.strategy)
        if not lexemes or total == 0:
            return []
        frequencies = self.document_frequencies(filters.strategy, lexemes)
        weights = [_idf(total, frequencies[lexeme]) for lexeme in lexemes]
        clauses, params = _filter_sql(filters, "c")
        sql = f"""
            SELECT c.id AS id,
                   sum(t.idf * ts_rank_cd(c.tsv, t.q::tsquery, {RANK_NORMALIZATION})) AS score
            FROM chunks c
            JOIN unnest(%s::text[], %s::float8[]) AS t(q, idf) ON c.tsv @@ t.q::tsquery
            WHERE {" AND ".join(clauses)}
            GROUP BY c.id
            ORDER BY score DESC, c.id
            LIMIT %s
        """
        args: list[Any] = [lexemes, weights, *params, k]
        with self.connection() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [(row["id"], float(row["score"])) for row in rows]

    def query_lexemes(self, query: str) -> list[str]:
        """Return the distinct query stems, each quoted so it casts straight to a tsquery."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT quote_literal(lexeme) AS q FROM unnest(to_tsvector('english', %s))",
                (query,),
            ).fetchall()
        return [row["q"] for row in rows]

    def chunk_count(self, strategy: str) -> int:
        """Count the chunks of one strategy; cached for the lifetime of this store."""
        if strategy not in self._chunk_count_cache:
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT count(*) AS n FROM chunks WHERE strategy = %s", (strategy,)
                ).fetchone()
            self._chunk_count_cache[strategy] = int(row["n"]) if row else 0
        return self._chunk_count_cache[strategy]

    def document_frequencies(self, strategy: str, lexemes: list[str]) -> dict[str, int]:
        """Count the chunks of the strategy holding each lexeme; cached per (strategy, term)."""
        missing = [lexeme for lexeme in lexemes if (strategy, lexeme) not in self._df_cache]
        if missing:
            with self.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT t.q AS q, count(c.id) AS df
                    FROM unnest(%s::text[]) AS t(q)
                    LEFT JOIN chunks c ON c.strategy = %s AND c.tsv @@ t.q::tsquery
                    GROUP BY t.q
                    """,
                    (missing, strategy),
                ).fetchall()
            for row in rows:
                self._df_cache[(strategy, row["q"])] = int(row["df"])
        return {lexeme: self._df_cache[(strategy, lexeme)] for lexeme in lexemes}

    def or_tsquery(self, query: str) -> str:
        """Parse the query into stems joined by OR, keeping quoted phrases as <-> groups."""
        for parser in TSQUERY_PARSERS:
            try:
                with self.connection() as conn:
                    row = conn.execute(
                        f"SELECT replace({parser}('english', %s)::text, ' & ', ' | ') AS q",
                        (query,),
                    ).fetchone()
            except psycopg.errors.SyntaxError:
                continue
            return str(row["q"]) if row and row["q"] else ""
        return ""

    # ------------------------------------------------------------ statistics

    def count_rows(self) -> list[tuple[str, int]]:
        with self.connection() as conn:
            counts = [
                (table, int(conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]))  # type: ignore[index]
                for table in COUNTED_TABLES
            ]
        return counts

    def count_chunks_by_strategy(self) -> list[tuple[str, int]]:
        return self._count_by("SELECT strategy AS key, count(*) AS n FROM chunks GROUP BY strategy")

    def count_embeddings_by_embedder(self) -> list[tuple[str, int]]:
        return self._count_by(
            "SELECT embedder AS key, count(*) AS n FROM embeddings GROUP BY embedder"
        )

    def _count_by(self, sql: str) -> list[tuple[str, int]]:
        with self.connection() as conn:
            rows = conn.execute(f"{sql} ORDER BY key").fetchall()
        return [(row["key"], int(row["n"])) for row in rows]


def _idf(total: int, frequency: int) -> float:
    """Smoothed inverse document frequency, always >= 1 so every term keeps some weight."""
    return math.log((total + 1) / (frequency + 1)) + 1.0


def _as_vector(vector: Vector) -> NDArray[np.float32]:
    return np.asarray(vector, dtype=np.float32)


def _filter_sql(filters: "SearchFilters", alias: str) -> tuple[list[str], list[Any]]:
    """Translate SearchFilters into SQL clauses on the chunks table alias."""
    clauses = [f"{alias}.strategy = %s"]
    params: list[Any] = [filters.strategy]
    if filters.course:
        clauses.append(f"{alias}.course = %s")
        params.append(filters.course)
    if filters.lab_id:
        clauses.append(f"{alias}.lab_id = %s")
        params.append(filters.lab_id)
    if filters.kinds:
        clauses.append(f"{alias}.kind = ANY(%s)")
        params.append(list(filters.kinds))
    return clauses, params
