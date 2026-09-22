"""
Role:   Integration tests for VectorStore and the searchers against a real Postgres with pgvector.
Input:  A running database at Settings.database_url (docker compose up -d db); no fixtures data.
Output: Assertions; every row written under strategy "test_fixed" is removed afterwards.
Flow:   Applies the schema, writes two documents with five chunks and their fake embeddings, then
        exercises lexical, idf-weighted lexical, dense and both hybrids plus the filters, and
        cleans up on teardown.
"""

from collections.abc import Iterator

import psycopg
import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import Chunk, ChunkKind, Course, Document, DocumentKind, Section
from rag_lab_generator.registry import create
from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.searchers.base import SearchFilters
from rag_lab_generator.retrieval.stores.vector_store import VectorStore

pytestmark = pytest.mark.integration

STRATEGY = "test_fixed"
EMBEDDER = "fake"
DOC_ID = "test/lab/integration"
OTHER_DOC_ID = "test/lab/integration_sop2"
TEXTS = {
    0: "Reading directory entries with readdir and closing the stream with closedir.",
    1: "Semaphores created with sem_open protect the critical section between processes.",
    2: "The inode keeps the metadata of a file, the directory keeps the name to inode mapping.",
    3: "Signal handlers installed with sigaction must stay async-signal-safe.",
}
# dense in the common stem "read" but free of the rare terms, to expose idf-less ranking
NOISE_TEXT = (
    "The worker copies bytes into the read buffer: read the header, read the payload, "
    "read the trailer, and read again until the socket is drained."
)


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(embedding_provider=EMBEDDER, embedding_dim=64)


@pytest.fixture(scope="module")
def store(settings: Settings) -> Iterator[VectorStore]:
    store = VectorStore(settings)
    try:
        with store.connection():
            pass
    except psycopg.Error as exc:
        pytest.skip(f"postgres not reachable at {settings.database_url}: {exc}")
    store.apply_schema()
    _seed(store, settings)
    yield store
    _cleanup(store)


@pytest.fixture(scope="module")
def embedder(settings: Settings) -> Embedder:
    model: Embedder = create("embedder", EMBEDDER, settings=settings)
    return model


def _documents() -> list[Document]:
    return [
        Document(
            id=DOC_ID,
            course=Course.SOP1,
            kind=DocumentKind.LAB,
            title="Integration lab",
            lab_id=DOC_ID,
            sections=[Section(id="s0", title="s0", text=TEXTS[0])],
        ),
        Document(
            id=OTHER_DOC_ID,
            course=Course.SOP2,
            kind=DocumentKind.LAB,
            title="Integration lab sop2",
            lab_id=OTHER_DOC_ID,
            sections=[Section(id="s0", title="s0", text=TEXTS[3])],
        ),
    ]


def _chunks() -> list[Chunk]:
    chunks = [
        Chunk(
            id=f"{STRATEGY}:{DOC_ID}:{idx}",
            document_id=DOC_ID,
            course=Course.SOP1,
            lab_id=DOC_ID,
            kind=ChunkKind.TUTORIAL if idx else ChunkKind.TASK,
            strategy=STRATEGY,
            idx=idx,
            text=text,
            section_id=f"s{idx}",
            parent_id=f"{STRATEGY}:{DOC_ID}:0" if idx == 2 else None,
        )
        for idx, text in TEXTS.items()
        if idx < 3
    ]
    chunks.append(
        Chunk(
            id=f"{STRATEGY}:{DOC_ID}:3",
            document_id=DOC_ID,
            course=Course.SOP1,
            lab_id=DOC_ID,
            kind=ChunkKind.TUTORIAL,
            strategy=STRATEGY,
            idx=3,
            text=NOISE_TEXT,
            section_id="s3",
        )
    )
    chunks.append(
        Chunk(
            id=f"{STRATEGY}:{OTHER_DOC_ID}:0",
            document_id=OTHER_DOC_ID,
            course=Course.SOP2,
            lab_id=OTHER_DOC_ID,
            kind=ChunkKind.TUTORIAL,
            strategy=STRATEGY,
            idx=0,
            text=TEXTS[3],
            section_id="s0",
        )
    )
    return chunks


def _seed(store: VectorStore, settings: Settings) -> None:
    """Write the fixture document, its chunks and their fake vectors."""
    store.upsert_documents(_documents())
    store.delete_chunks(STRATEGY)
    chunks = _chunks()
    store.upsert_chunks(chunks)
    model: Embedder = create("embedder", EMBEDDER, settings=settings)
    vectors = model.embed_documents([c.text for c in chunks])
    store.upsert_embeddings(EMBEDDER, [c.id for c in chunks], vectors)


def _cleanup(store: VectorStore) -> None:
    store.delete_chunks(STRATEGY)
    with store.connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = ANY(%s)", ([DOC_ID, OTHER_DOC_ID],))
        conn.commit()


def test_apply_schema_is_idempotent(store: VectorStore) -> None:
    store.apply_schema()
    store.apply_schema()


def test_chunks_round_trip(store: VectorStore) -> None:
    stored = store.list_chunks(STRATEGY, lab_id=DOC_ID)
    assert [c.idx for c in stored] == [0, 1, 2, 3]
    assert stored[2].parent_id == f"{STRATEGY}:{DOC_ID}:0"
    assert stored[0].kind == ChunkKind.TASK


def test_lexical_search_finds_the_distinctive_chunk(store: VectorStore) -> None:
    hits = store.lexical_search("readdir closedir", 5, SearchFilters(strategy=STRATEGY))
    assert hits
    assert hits[0][0] == f"{STRATEGY}:{DOC_ID}:0"
    assert hits[0][1] > 0


def test_lexical_search_survives_odd_syntax(store: VectorStore) -> None:
    hits = store.lexical_search('semaphores "', 5, SearchFilters(strategy=STRATEGY))
    assert hits[0][0] == f"{STRATEGY}:{DOC_ID}:1"


def test_lexical_search_ors_the_terms(store: VectorStore) -> None:
    """A natural language question must not be AND-ed into a single-chunk result."""
    query = "how to read directory entries with readdir"
    hits = store.lexical_search(query, 8, SearchFilters(strategy=STRATEGY))
    ids = [chunk_id for chunk_id, _ in hits]
    assert len(hits) > 1
    assert f"{STRATEGY}:{DOC_ID}:0" in ids
    assert f"{STRATEGY}:{DOC_ID}:2" in ids
    assert hits[0][1] > hits[-1][1]


def test_plain_ranking_favours_the_read_dense_chunk(store: VectorStore) -> None:
    """Without idf the chunk repeating the common stem "read" wins; lexical_idf fixes this."""
    query = "how to read directory entries with readdir"
    ids = [
        chunk_id for chunk_id, _ in store.lexical_search(query, 8, SearchFilters(strategy=STRATEGY))
    ]
    assert ids.index(f"{STRATEGY}:{DOC_ID}:3") < ids.index(f"{STRATEGY}:{DOC_ID}:0")


def test_lexical_idf_outranks_the_read_dense_chunk(store: VectorStore) -> None:
    query = "how to read directory entries with readdir"
    hits = store.lexical_search_idf(query, 8, SearchFilters(strategy=STRATEGY))
    ids = [chunk_id for chunk_id, _ in hits]
    assert ids[0] == f"{STRATEGY}:{DOC_ID}:0"
    assert ids.index(f"{STRATEGY}:{DOC_ID}:0") < ids.index(f"{STRATEGY}:{DOC_ID}:3")
    assert hits[0][1] > hits[1][1]


def test_idf_weights_rare_terms_higher(store: VectorStore) -> None:
    lexemes = store.query_lexemes("how to read directory entries with readdir")
    frequencies = store.document_frequencies(STRATEGY, lexemes)
    assert frequencies["'readdir'"] < frequencies["'read'"]
    assert store.chunk_count(STRATEGY) == len(_chunks())
    # second call must be served from the instance cache
    assert store.document_frequencies(STRATEGY, lexemes) == frequencies


def test_lexical_search_keeps_phrases_and_drops_stopword_queries(store: VectorStore) -> None:
    assert store.or_tsquery('read "directory entries"') == "'read' | 'directori' <-> 'entri'"
    assert store.or_tsquery("the of and") == ""
    assert store.lexical_search("the of and", 5, SearchFilters(strategy=STRATEGY)) == []


def test_dense_search_returns_the_exact_text_first(store: VectorStore, embedder: Embedder) -> None:
    query_vec = embedder.embed_query(TEXTS[1])
    hits = store.dense_search(query_vec, EMBEDDER, 5, SearchFilters(strategy=STRATEGY))
    assert hits[0][0] == f"{STRATEGY}:{DOC_ID}:1"
    assert hits[0][1] == pytest.approx(1.0, abs=1e-5)


def test_filters_restrict_the_result_set(store: VectorStore, embedder: Embedder) -> None:
    filters = SearchFilters(strategy=STRATEGY, course="sop2")
    hits = store.dense_search(embedder.embed_query(TEXTS[3]), EMBEDDER, 5, filters)
    assert [chunk_id for chunk_id, _ in hits] == [f"{STRATEGY}:{OTHER_DOC_ID}:0"]
    kinds = SearchFilters(strategy=STRATEGY, kinds=["task"])
    assert store.lexical_search("readdir", 5, kinds)[0][0] == f"{STRATEGY}:{DOC_ID}:0"
    assert store.lexical_search("inode", 5, kinds) == []


def test_hybrid_combines_both_rankings(
    store: VectorStore, embedder: Embedder, settings: Settings
) -> None:
    searcher = create("searcher", "hybrid_rrf", store=store, embedder=embedder, settings=settings)
    hits = searcher.search(TEXTS[0], 4, SearchFilters(strategy=STRATEGY))
    assert hits[0].chunk.id == f"{STRATEGY}:{DOC_ID}:0"
    assert hits[0].source == "hybrid_rrf"
    ranks = hits[0].chunk.metadata["ranks"]
    assert set(ranks) == {"lexical", "dense"}
    assert ranks["dense"] == 1


def test_hybrid_idf_uses_the_idf_lexical_side(
    store: VectorStore, embedder: Embedder, settings: Settings
) -> None:
    searcher = create(
        "searcher", "hybrid_rrf_idf", store=store, embedder=embedder, settings=settings
    )
    assert searcher.lexical_name == "lexical_idf"
    assert searcher.lexical_searcher().name == "lexical_idf"
    hits = searcher.search(
        "how to read directory entries with readdir", 4, SearchFilters(strategy=STRATEGY)
    )
    assert hits[0].source == "hybrid_rrf_idf"
    assert set(hits[0].chunk.metadata["ranks"]) <= {"lexical_idf", "dense"}
    ranked = {hit.chunk.id: hit.chunk.metadata["ranks"] for hit in hits}
    assert ranked[f"{STRATEGY}:{DOC_ID}:0"]["lexical_idf"] == 1


def test_vector_rag_expands_the_parent(
    store: VectorStore, embedder: Embedder, settings: Settings
) -> None:
    searcher = create("searcher", "dense", store=store, embedder=embedder, settings=settings)
    rag = create("rag", "vector", searcher=searcher, store=store, settings=settings)
    context = rag.retrieve(TEXTS[2], 1, SearchFilters(strategy=STRATEGY))
    ids = [scored.chunk.id for scored in context.chunks]
    assert ids == [f"{STRATEGY}:{DOC_ID}:2", f"{STRATEGY}:{DOC_ID}:0"]
    assert context.chunks[1].source == "parent_expansion"


def test_embeddings_are_replaced_not_duplicated(store: VectorStore, embedder: Embedder) -> None:
    chunk_id = f"{STRATEGY}:{DOC_ID}:0"
    before = dict(store.count_embeddings_by_embedder())[EMBEDDER]
    store.upsert_embeddings(EMBEDDER, [chunk_id], [embedder.embed_query(TEXTS[0])])
    assert dict(store.count_embeddings_by_embedder())[EMBEDDER] == before
    assert store.chunks_without_embeddings(EMBEDDER, STRATEGY) == []
