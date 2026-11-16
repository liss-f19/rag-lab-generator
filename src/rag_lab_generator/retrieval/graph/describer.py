"""
Role:   Generates the short description shown for a graph node instead of its raw chunks.
Input:  GraphStore (nodes, node_chunks, chunks, node_descriptions), an LLM, node kinds, force.
Output: NodeDescription rows upserted into node_descriptions; DescribeReport with counts.
Flow:   Lists the nodes of the wanted kinds, ranks each node's chunks (lab text first, lecture
        pages next, code last) into a bounded excerpt list, hashes chunk ids + model + prompt
        version, skips nodes whose hash is already stored unless forced, otherwise asks the LLM
        with the describe_node prompt and stores the answer.
"""

import hashlib
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from rag_lab_generator.generation.llm.base import LLM
from rag_lab_generator.generation.prompts import load_prompt
from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    GraphNode,
    LLMMessage,
    NodeDescription,
    NodeKind,
)
from rag_lab_generator.retrieval.stores.graph_store import GraphStore

PROMPT_NAME = "describe_node"
PROMPT_VERSION = "1"
DEFAULT_KINDS: tuple[NodeKind, ...] = (NodeKind.CONCEPT, NodeKind.API_FUNCTION, NodeKind.LECTURE)
MAX_SOURCE_CHUNKS = 8
MAX_SOURCE_CHARS = 9000
EXCERPT_CHARS = 1200
MAX_TOKENS = 400
KIND_RANK: dict[ChunkKind, int] = {
    ChunkKind.TASK: 0,
    ChunkKind.TUTORIAL: 1,
    ChunkKind.SUMMARY: 2,
    ChunkKind.LECTURE: 3,
    ChunkKind.INFO: 4,
    ChunkKind.CODE: 5,
}


class DescribeReport(BaseModel):
    """What one graph-describe run did."""

    model: str = ""
    considered: int = 0
    generated: int = 0
    skipped_unchanged: int = 0
    skipped_empty: int = 0


def describe_nodes(
    store: GraphStore,
    llm: LLM,
    kinds: Sequence[NodeKind] | None = None,
    force: bool = False,
    limit: int | None = None,
    progress: Callable[[GraphNode], None] | None = None,
) -> DescribeReport:
    """Generate the missing or outdated descriptions of the nodes of the given kinds."""
    nodes = store.list_nodes(list(kinds or DEFAULT_KINDS))
    if limit:
        nodes = nodes[:limit]
    existing = store.descriptions_for([node.id for node in nodes])
    # Provider and model together: a fake stub must never pass for a real model's text.
    model_id = f"{llm.name}/{llm.model}"
    report = DescribeReport(model=model_id, considered=len(nodes))
    for node in nodes:
        sources = select_sources(list(store.fetch_chunks(node.chunk_ids).values()))
        if not sources:
            report.skipped_empty += 1
            continue
        digest = source_hash(sources, model_id)
        cached = existing.get(node.id)
        if cached is not None and cached.source_hash == digest and not force:
            report.skipped_unchanged += 1
            continue
        text = generate_description(node, sources, llm)
        store.upsert_descriptions(
            [NodeDescription(node_id=node.id, text=text, source_hash=digest, model=model_id)]
        )
        report.generated += 1
        if progress is not None:
            progress(node)
    return report


def select_sources(chunks: list[Chunk]) -> list[Chunk]:
    """Keep the most informative chunks of a node within the chunk and character budgets."""
    ranked = sorted(chunks, key=lambda c: (KIND_RANK.get(c.kind, 9), c.document_id, c.idx))
    kept: list[Chunk] = []
    used = 0
    for chunk in ranked:
        cost = min(len(chunk.text), EXCERPT_CHARS)
        if len(kept) >= MAX_SOURCE_CHUNKS or used + cost > MAX_SOURCE_CHARS:
            break
        kept.append(chunk)
        used += cost
    return kept


def source_hash(sources: list[Chunk], model: str) -> str:
    """Fingerprint of the exact inputs a description was generated from."""
    material = "|".join(sorted(chunk.id for chunk in sources)) + f"|{model}|{PROMPT_VERSION}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_user_prompt(node: GraphNode, sources: list[Chunk]) -> str:
    """Node line, the documents it appears in, then one numbered excerpt per source chunk."""
    documents = sorted({chunk.document_id for chunk in sources})
    lines = [
        f"{node.label} ({node.kind.value}) appears in: {', '.join(documents)}.",
        "",
        "Sources:",
    ]
    for number, chunk in enumerate(sources, start=1):
        where = chunk.section_id or f"chunk {chunk.idx}"
        excerpt = chunk.text.strip()[:EXCERPT_CHARS]
        lines += [f"[{number}] {chunk.document_id} - {where}", excerpt, ""]
    return "\n".join(lines).rstrip()


def generate_description(node: GraphNode, sources: list[Chunk], llm: LLM) -> str:
    """Ask the LLM for the description of one node."""
    response = llm.complete(
        [LLMMessage(role="user", content=build_user_prompt(node, sources))],
        system=load_prompt(PROMPT_NAME),
        max_tokens=MAX_TOKENS,
    )
    return response.text.strip()
