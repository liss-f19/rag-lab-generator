"""
Role:   Postgres persistence and in-memory view of the knowledge graph used by GraphRAG.
Input:  Settings.database_url through PostgresStore; GraphNode / GraphEdge models to persist.
Output: Rows in nodes / node_chunks / edges, a networkx.MultiDiGraph and chunk<->node lookups.
Flow:   replace_graph() wipes and rewrites the three graph tables in one transaction;
        upsert_nodes/upsert_edges write incrementally; load_graph() reads every row once and
        caches a MultiDiGraph keyed by edge kind on the instance; the lookup helpers answer
        chunk<->node questions in one round trip; find_nodes() uses the lower(label) index.
"""

from __future__ import annotations

import json
from typing import Any

import networkx as nx

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Course, EdgeKind, GraphEdge, GraphNode, NodeKind
from rag_lab_generator.retrieval.stores.postgres import PostgresStore


def graph_from(nodes: list[GraphNode], edges: list[GraphEdge]) -> nx.MultiDiGraph[str]:
    """Build the walker view; a MultiDiGraph keeps parallel edges of different kinds."""
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(
            node.id,
            kind=node.kind.value,
            label=node.label,
            course=node.course.value if node.course else None,
            lab_id=node.lab_id,
            document_id=node.document_id,
            properties=node.properties,
            chunk_ids=list(node.chunk_ids),
        )
    for edge in edges:
        if graph.has_node(edge.src) and graph.has_node(edge.dst):
            graph.add_edge(
                edge.src,
                edge.dst,
                key=edge.kind.value,
                kind=edge.kind.value,
                weight=edge.weight,
            )
    return graph


class GraphStore(PostgresStore):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._graph: nx.MultiDiGraph[str] | None = None

    # ------------------------------------------------------------ writes

    def replace_graph(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, int]:
        """Rewrite the whole graph in one transaction and drop the cached DiGraph."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM edges")
            cur.execute("DELETE FROM node_chunks")
            cur.execute("DELETE FROM nodes")
            cur.executemany(_INSERT_NODE, [_node_row(n) for n in nodes])
            cur.executemany(_INSERT_NODE_CHUNK, _node_chunk_rows(nodes))
            cur.executemany(_INSERT_EDGE, [_edge_row(e) for e in edges])
            conn.commit()
        self._graph = None
        return {"nodes": len(nodes), "edges": len(edges)}

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        if not nodes:
            return
        with self.connection() as conn, conn.cursor() as cur:
            cur.executemany(_INSERT_NODE, [_node_row(n) for n in nodes])
            cur.execute("DELETE FROM node_chunks WHERE node_id = ANY(%s)", ([n.id for n in nodes],))
            cur.executemany(_INSERT_NODE_CHUNK, _node_chunk_rows(nodes))
            conn.commit()
        self._graph = None

    def upsert_edges(self, edges: list[GraphEdge]) -> None:
        if not edges:
            return
        with self.connection() as conn, conn.cursor() as cur:
            cur.executemany(_INSERT_EDGE, [_edge_row(e) for e in edges])
            conn.commit()
        self._graph = None

    # ------------------------------------------------------------ reads

    def load_graph(self, refresh: bool = False) -> nx.MultiDiGraph[str]:
        """Read nodes, their chunk ids and edges once and cache the DiGraph on this instance."""
        if self._graph is not None and not refresh:
            return self._graph
        self._graph = graph_from(self.list_nodes(), self.list_edges())
        return self._graph

    def list_nodes(self) -> list[GraphNode]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT n.*, COALESCE(
                    (SELECT array_agg(nc.chunk_id ORDER BY nc.chunk_id)
                     FROM node_chunks nc WHERE nc.node_id = n.id), '{}') AS chunk_ids
                FROM nodes n ORDER BY n.id
                """
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def list_edges(self) -> list[GraphEdge]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM edges ORDER BY src, dst, kind").fetchall()
        return [
            GraphEdge(
                src=row["src"],
                dst=row["dst"],
                kind=EdgeKind(row["kind"]),
                weight=float(row["weight"]),
                properties=_as_dict(row["properties"]),
            )
            for row in rows
        ]

    def nodes_for_chunks(self, chunk_ids: list[str]) -> dict[str, list[str]]:
        if not chunk_ids:
            return {}
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, node_id FROM node_chunks WHERE chunk_id = ANY(%s)"
                " ORDER BY chunk_id, node_id",
                (chunk_ids,),
            ).fetchall()
        result: dict[str, list[str]] = {}
        for row in rows:
            result.setdefault(row["chunk_id"], []).append(row["node_id"])
        return result

    def chunks_for_nodes(self, node_ids: list[str]) -> dict[str, list[str]]:
        if not node_ids:
            return {}
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT node_id, chunk_id FROM node_chunks WHERE node_id = ANY(%s)"
                " ORDER BY node_id, chunk_id",
                (node_ids,),
            ).fetchall()
        result: dict[str, list[str]] = {}
        for row in rows:
            result.setdefault(row["node_id"], []).append(row["chunk_id"])
        return result

    def find_nodes(self, label_query: str, kinds: list[NodeKind] | None = None) -> list[GraphNode]:
        """Case-insensitive substring match on the label, shortest labels first."""
        sql = [
            "SELECT n.*, '{}'::text[] AS chunk_ids FROM nodes n WHERE lower(n.label) LIKE %s",
        ]
        params: list[Any] = [f"%{label_query.lower()}%"]
        if kinds:
            sql.append("AND n.kind = ANY(%s)")
            params.append([k.value for k in kinds])
        sql.append("ORDER BY length(n.label), n.label LIMIT 50")
        with self.connection() as conn:
            rows = conn.execute(" ".join(sql), params).fetchall()
        return [_row_to_node(row) for row in rows]

    def stats(self) -> dict[str, int]:
        """Counts per node kind and per edge kind plus the node<->chunk attachment count."""
        counts: dict[str, int] = {}
        with self.connection() as conn:
            for row in conn.execute("SELECT kind, count(*) AS n FROM nodes GROUP BY kind"):
                counts[f"node:{row['kind']}"] = int(row["n"])
            for row in conn.execute("SELECT kind, count(*) AS n FROM edges GROUP BY kind"):
                counts[f"edge:{row['kind']}"] = int(row["n"])
            for table in ("nodes", "edges", "node_chunks"):
                total = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
                counts[table] = int(total["n"]) if total else 0
        return dict(sorted(counts.items()))


_INSERT_NODE = """
    INSERT INTO nodes (id, kind, label, course, lab_id, document_id, properties)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        kind = EXCLUDED.kind, label = EXCLUDED.label, course = EXCLUDED.course,
        lab_id = EXCLUDED.lab_id, document_id = EXCLUDED.document_id,
        properties = EXCLUDED.properties
"""

# Attach a chunk only when it is present, so a stale chunk id never breaks the build.
_INSERT_NODE_CHUNK = """
    INSERT INTO node_chunks (node_id, chunk_id)
    SELECT %s, %s WHERE EXISTS (SELECT 1 FROM chunks WHERE id = %s)
    ON CONFLICT DO NOTHING
"""

_INSERT_EDGE = """
    INSERT INTO edges (src, dst, kind, weight, properties)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (src, dst, kind) DO UPDATE SET
        weight = EXCLUDED.weight, properties = EXCLUDED.properties
"""


def _node_row(node: GraphNode) -> tuple[Any, ...]:
    return (
        node.id,
        node.kind.value,
        node.label,
        node.course.value if node.course else None,
        node.lab_id,
        node.document_id,
        json.dumps(node.properties, default=str),
    )


def _node_chunk_rows(nodes: list[GraphNode]) -> list[tuple[str, str, str]]:
    return [(n.id, c, c) for n in nodes for c in dict.fromkeys(n.chunk_ids)]


def _edge_row(edge: GraphEdge) -> tuple[Any, ...]:
    return (
        edge.src,
        edge.dst,
        edge.kind.value,
        edge.weight,
        json.dumps(edge.properties, default=str),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    loaded: Any = json.loads(value) if value else {}
    return loaded if isinstance(loaded, dict) else {}


def _row_to_node(row: dict[str, Any]) -> GraphNode:
    return GraphNode(
        id=row["id"],
        kind=NodeKind(row["kind"]),
        label=row["label"],
        course=Course(row["course"]) if row["course"] else None,
        lab_id=row["lab_id"],
        document_id=row["document_id"],
        chunk_ids=list(row.get("chunk_ids") or []),
        properties=_as_dict(row["properties"]),
    )
