"""
Role:   Default RAG strategy: plain vector retrieval with parent-chunk expansion.
Input:  Query, k and SearchFilters; a Searcher and the chunk store.
Output: RetrievedContext with deduplicated chunks and a timing trace.
Flow:   Runs the searcher, drops duplicate chunk ids keeping the best score, then fetches the
        parent chunk of every hierarchical hit that is not already present and adds it with a
        damped score; the result stays sorted by score and the trace records searcher name, k,
        latency and the expansion count.
"""

from time import perf_counter

from rag_lab_generator.models import RetrievedContext, ScoredChunk
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.searchers.base import SearchFilters

PARENT_SCORE_FACTOR = 0.5
PARENT_SOURCE = "parent_expansion"


@register("rag", "vector")
class VectorRAG(RAG):
    name = "vector"

    def retrieve(self, query: str, k: int, filters: SearchFilters) -> RetrievedContext:
        started = perf_counter()
        hits = _dedupe(self.searcher.search(query, k, filters))
        parents = self._expand_parents(hits)
        # keep the whole context ranked, expanded parents included
        ranked = sorted([*hits, *parents], key=lambda scored: -scored.score)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return RetrievedContext(
            query=query,
            rag=self.name,
            chunks=ranked,
            trace={
                "searcher": self.searcher.name,
                "k": k,
                "latency_ms": round(elapsed_ms, 3),
                "n_hits": len(hits),
                "n_parents": len(parents),
            },
        )

    def _expand_parents(self, hits: list[ScoredChunk]) -> list[ScoredChunk]:
        """Append the parent chunk of every hit whose parent is missing from the result list."""
        present = {hit.chunk.id for hit in hits}
        wanted: dict[str, float] = {}
        for hit in hits:
            parent_id = hit.chunk.parent_id
            if parent_id and parent_id not in present:
                wanted[parent_id] = max(wanted.get(parent_id, 0.0), hit.score)
        if not wanted:
            return []
        fetched = self.store.fetch_chunks(list(wanted))
        return [
            ScoredChunk(
                chunk=chunk,
                score=wanted[parent_id] * PARENT_SCORE_FACTOR,
                source=PARENT_SOURCE,
            )
            for parent_id, chunk in fetched.items()
        ]


def _dedupe(hits: list[ScoredChunk]) -> list[ScoredChunk]:
    seen: set[str] = set()
    out: list[ScoredChunk] = []
    for hit in hits:
        if hit.chunk.id in seen:
            continue
        seen.add(hit.chunk.id)
        out.append(hit)
    return out
