"""
Role:   Orchestrates one full knowledge-graph build: documents + chunks -> nodes/edges -> Postgres.
Input:  Settings, the chunking strategy whose chunks the nodes are attached to, optional courses.
Output: Counts of documents, chunks, nodes and edges written, merged with GraphStore.stats().
Flow:   Load documents through the ingestion pipeline, make sure they exist in the documents
        table, read the chunks of the requested strategy, run the deterministic extractor and
        replace the whole graph in one transaction.
"""

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, Document
from rag_lab_generator.retrieval.graph.extractor import extract_graph
from rag_lab_generator.retrieval.stores.graph_store import GraphStore


def build_graph(
    settings: Settings, strategy: str, courses: list[str] | None = None
) -> dict[str, int]:
    """Rebuild the knowledge graph from the ingested corpus and the chunks of one strategy."""
    # imported lazily so the graph package does not depend on ingestion at import time
    from rag_lab_generator.ingestion.pipeline import load_documents

    docs: list[Document] = load_documents(settings, courses=courses)
    store = GraphStore(settings)
    store.upsert_documents(docs)
    chunks: list[Chunk] = store.list_chunks(strategy)
    if courses:
        wanted = set(courses)
        docs = [d for d in docs if d.course.value in wanted]
        chunks = [c for c in chunks if c.course.value in wanted]
    nodes, edges = extract_graph(docs, chunks)
    store.replace_graph(nodes, edges)
    stats = {
        "documents": len(docs),
        "chunks": len(chunks),
        "nodes": len(nodes),
        "edges": len(edges),
    }
    stats.update(store.stats())
    return stats
