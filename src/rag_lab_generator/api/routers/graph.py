"""
Role:   Knowledge graph endpoints backing the graph explorer page.
Input:  node ids, label queries and a hop count; GraphStore rows in Postgres.
Output: SubgraphResponse (nodes + edges), GraphStatsResponse, NodeChunksResponse.
Flow:   Every route opens a GraphStore lazily (503 when the store or the database is missing),
        loads the cached DiGraph, expands a breadth-first neighbourhood up to `hops` while
        capping the node count, and projects nodes and edges onto the response schemas.
"""

from collections import deque
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from rag_lab_generator.api import deps
from rag_lab_generator.api.schemas import (
    ChunkPreview,
    GraphEdgeOut,
    GraphNodeOut,
    GraphStatsResponse,
    NodeChunksResponse,
    NodeDescriptionOut,
    NodeSourceOut,
    SubgraphResponse,
)
from rag_lab_generator.config import Settings
from rag_lab_generator.retrieval.graph.sources import group_sources

router = APIRouter(prefix="/api/graph", tags=["graph"])

MAX_NODES = 150
MAX_HOPS = 3


def settings_of(request: Request) -> Settings:
    state: Settings = request.app.state.settings
    return state


def _load(settings: Settings) -> Any:
    store = deps.open_graph_store(settings)
    with deps.translate("the knowledge graph"):
        return store.load_graph()


def _node_out(graph: Any, node_id: str, hops: int | None) -> GraphNodeOut:
    data: dict[str, Any] = graph.nodes[node_id]
    return GraphNodeOut(
        id=node_id,
        kind=str(data.get("kind", "concept")),
        label=str(data.get("label", node_id)),
        course=data.get("course"),
        lab_id=data.get("lab_id"),
        document_id=data.get("document_id"),
        chunk_ids=list(data.get("chunk_ids") or []),
        degree=int(graph.degree(node_id)),
        hops=hops,
    )


def _edges_between(graph: Any, ids: set[str]) -> list[GraphEdgeOut]:
    return [
        GraphEdgeOut(
            src=src,
            dst=dst,
            kind=str(data.get("kind", "related_to")),
            weight=float(data.get("weight", 1.0)),
        )
        for src, dst, data in graph.edges(data=True)
        if src in ids and dst in ids
    ]


def _neighbourhood(graph: Any, node_id: str, hops: int) -> dict[str, int]:
    """Breadth-first expansion ignoring edge direction, capped at MAX_NODES."""
    distance: dict[str, int] = {node_id: 0}
    queue: deque[str] = deque([node_id])
    while queue and len(distance) < MAX_NODES:
        current = queue.popleft()
        if distance[current] >= hops:
            continue
        for neighbour in set(graph.successors(current)) | set(graph.predecessors(current)):
            if neighbour not in distance:
                distance[neighbour] = distance[current] + 1
                queue.append(neighbour)
                if len(distance) >= MAX_NODES:
                    break
    return distance


@router.get("/neighbors", response_model=SubgraphResponse)
async def neighbors(
    request: Request,
    node_id: str = Query(min_length=1),
    hops: int = Query(default=1, ge=1, le=MAX_HOPS),
) -> SubgraphResponse:
    """Subgraph around one node up to `hops` edges away, in both directions."""
    settings = settings_of(request)
    graph = await run_in_threadpool(_load, settings)
    if not graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"no graph node {node_id!r}")
    distance = _neighbourhood(graph, node_id, hops)
    return SubgraphResponse(
        center=node_id,
        hops=hops,
        nodes=[_node_out(graph, nid, dist) for nid, dist in distance.items()],
        edges=_edges_between(graph, set(distance)),
    )


@router.get("/search", response_model=SubgraphResponse)
async def search(
    request: Request,
    q: str = Query(min_length=1),
    limit: int = Query(default=30, ge=1, le=MAX_NODES),
) -> SubgraphResponse:
    """Nodes whose label matches the query, plus the edges connecting the matches."""
    settings = settings_of(request)
    graph = await run_in_threadpool(_load, settings)
    needle = q.lower()
    matched = [
        nid for nid, data in graph.nodes(data=True) if needle in str(data.get("label", "")).lower()
    ]
    matched.sort(key=lambda nid: (len(str(graph.nodes[nid].get("label", nid))), nid))
    selected = matched[:limit]
    return SubgraphResponse(
        center=None,
        hops=0,
        nodes=[_node_out(graph, nid, None) for nid in selected],
        edges=_edges_between(graph, set(selected)),
    )


@router.get("/stats", response_model=GraphStatsResponse)
async def stats(request: Request) -> GraphStatsResponse:
    """Node and edge counts per kind, straight from the graph tables."""
    settings = settings_of(request)
    store = deps.open_graph_store(settings)
    with deps.translate("the knowledge graph statistics"):
        counts = await run_in_threadpool(store.stats)
    return GraphStatsResponse(counts=dict(counts))


@router.get("/chunks", response_model=NodeChunksResponse)
async def node_chunks(request: Request, node_id: str = Query(min_length=1)) -> NodeChunksResponse:
    """Chunk texts attached to one node, for the details panel of the graph page."""
    settings = settings_of(request)
    store = deps.open_graph_store(settings)
    with deps.translate("the chunks of the node"):
        mapping = await run_in_threadpool(store.chunks_for_nodes, [node_id])
        chunk_ids = list(mapping.get(node_id, []))
        fetched = await run_in_threadpool(store.fetch_chunks, chunk_ids)
        document_ids = sorted({chunk.document_id for chunk in fetched.values()})
        headers = await run_in_threadpool(store.fetch_document_headers, document_ids)
        described = await run_in_threadpool(store.descriptions_for, [node_id])
    description = described.get(node_id)
    return NodeChunksResponse(
        node_id=node_id,
        description=(
            NodeDescriptionOut(
                text=description.text,
                model=description.model,
                generated_at=description.generated_at,
            )
            if description is not None
            else None
        ),
        sources=[
            NodeSourceOut.model_validate(source.model_dump(mode="json"))
            for source in group_sources(list(fetched.values()), headers)
        ],
        chunks=[
            ChunkPreview(
                id=chunk.id,
                document_id=chunk.document_id,
                lab_id=chunk.lab_id,
                kind=chunk.kind.value,
                section_id=chunk.section_id,
                text=chunk.text,
            )
            for chunk in fetched.values()
        ],
    )
