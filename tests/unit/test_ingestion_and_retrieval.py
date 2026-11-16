"""Ingestion, indexing, and vector retrieval through the application services."""

from uuid import UUID

import pytest

from rag_lab_generator.domain.errors import EmptyDocumentError, ExtractionError
from rag_lab_generator.domain.models import (
    DocumentMetadata,
    IngestionStatus,
    KnowledgeBaseRole,
    RetrievalQuery,
    User,
    UserRole,
)
from rag_lab_generator.domain.policy import EvidencePurpose, SourceAuthorityPolicy
from rag_lab_generator.infrastructure.embeddings import HashingEmbeddingClient
from rag_lab_generator.ingestion.chunking import StructuredChunker
from rag_lab_generator.ingestion.service import IngestionService
from rag_lab_generator.retrieval.service import RetrievalService
from rag_lab_generator.retrieval.vector import VectorRetrievalStrategy
from tests.conftest import AppEnvironment, build_environment

MUTEX = b"""# Synchronization
## Mutex
A mutex protects a critical section so that only one thread enters it.
## Barrier
A barrier makes all threads wait until every thread arrives.
"""
PIPES = b"""# Pipes
## Pipe
A pipe transfers bytes from the writing process to the reading process.
"""


@pytest.fixture(name="queued_env")
def queued_env_fixture(tmp_path) -> AppEnvironment:  # type: ignore[no-untyped-def]
    """Uploads are queued but not run, so the services can be called directly."""
    return build_environment(tmp_path, inline=False)


def _services(env: AppEnvironment) -> tuple[IngestionService, VectorRetrievalStrategy]:
    embedder = HashingEmbeddingClient(256)
    container = env.container
    ingestion = IngestionService(
        documents=container.documents,
        files=container.files,
        chunker=StructuredChunker(400, 50),
        embedder=embedder,
        index=env.index,
    )
    retrieval = VectorRetrievalStrategy(
        documents=container.documents, embedder=embedder, index=env.index
    )
    return ingestion, retrieval


def _upload(
    env: AppEnvironment,
    user: User,
    data: bytes,
    base: KnowledgeBaseRole = KnowledgeBaseRole.PRIMARY,
    filename: str = "notes.md",
    **metadata: str,
) -> UUID:
    document, _ = env.container.document_service.upload(
        filename=filename,
        data=data,
        metadata=DocumentMetadata(course_id="sop", knowledge_base=base, **metadata),
        user=user,
    )
    return document.document_id


def test_ingestion_stores_fragments_and_vectors(queued_env: AppEnvironment) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, MUTEX)
    ingestion, _ = _services(queued_env)

    result = ingestion.ingest(document_id)

    assert result["chunk_count"] == 2
    assert result["embedding_model"] == "hashing-bow-256"
    assert set(result["timings_ms"]) == {
        "extract_ms",
        "chunk_ms",
        "embed_ms",
        "persist_ms",
        "index_ms",
    }
    document = queued_env.container.documents.get_document(document_id)
    assert document.ingestion_status is IngestionStatus.INDEXED
    chunks = queued_env.container.documents.list_chunks(document_id)
    assert [chunk.section_path for chunk in chunks] == [
        ("Synchronization", "Mutex"),
        ("Synchronization", "Barrier"),
    ]
    vectors = queued_env.index.collections[result["collection"]]
    assert set(vectors) == {chunk.chroma_record_id for chunk in chunks}
    assert {meta["knowledge_base"] for _, meta in vectors.values()} == {"primary"}


def test_reingestion_replaces_fragments_and_vectors(queued_env: AppEnvironment) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, MUTEX)
    ingestion, _ = _services(queued_env)
    first = ingestion.ingest(document_id)
    second = ingestion.ingest(document_id)
    assert (
        len(queued_env.index.collections[first["collection"]])
        == second["chunk_count"]
        == 2
    )
    assert len(queued_env.container.documents.list_chunks(document_id)) == 2


@pytest.mark.parametrize(
    ("data", "filename", "error"),
    [
        (b"   \n\n  ", "blank.md", EmptyDocumentError),
        (b"\xff\xfe\x00bad", "bad.txt", ExtractionError),
    ],
)
def test_failed_extraction_marks_the_document_failed(
    queued_env: AppEnvironment, data: bytes, filename: str, error: type[Exception]
) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, data, filename=filename)
    ingestion, _ = _services(queued_env)
    with pytest.raises(error):
        ingestion.ingest(document_id)
    document = queued_env.container.documents.get_document(document_id)
    assert document.ingestion_status is IngestionStatus.FAILED
    assert document.error_message


def test_unexpected_errors_also_mark_the_document_failed(
    queued_env: AppEnvironment,
) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, MUTEX)
    ingestion, _ = _services(queued_env)

    def broken_upsert(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("disk full")

    queued_env.index.upsert = broken_upsert  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        ingestion.ingest(document_id)
    document = queued_env.container.documents.get_document(document_id)
    assert document.ingestion_status is IngestionStatus.FAILED
    assert document.error_message == "Internal error during ingestion."


def test_course_indexing_continues_after_a_failed_document(
    queued_env: AppEnvironment,
) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    _upload(queued_env, user, MUTEX)
    broken = _upload(queued_env, user, b"\n\n", filename="empty.md")
    ingestion, _ = _services(queued_env)
    result = ingestion.index_course("sop")
    assert (result["documents"], result["indexed"], result["chunk_count"]) == (2, 1, 2)
    assert result["failed"][0]["document_id"] == str(broken)


def test_retrieval_ranks_relevant_fragments_and_applies_the_policy(
    queued_env: AppEnvironment,
) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    primary = _upload(queued_env, user, MUTEX, document_type="tutorial")
    # The same text in the supplementary base: equal similarity, lower rank.
    supplementary = _upload(
        queued_env,
        user,
        b"# Synchronization\n## Mutex\n"
        b"A mutex protects a critical section so that only one thread enters it.",
        KnowledgeBaseRole.SUPPLEMENTARY,
    )
    pipes = _upload(queued_env, user, PIPES, document_type="lab_task")
    not_indexed = _upload(queued_env, user, MUTEX)
    ingestion, retrieval = _services(queued_env)
    for document_id in (primary, supplementary, pipes):
        ingestion.ingest(document_id)

    query = RetrievalQuery(
        course_id="sop", text="how does a mutex protect a critical section"
    )
    context = retrieval.retrieve(
        query, SourceAuthorityPolicy.for_purpose(EvidencePurpose.CONTEXT), 3
    )
    assert context[0].document_id == primary
    assert context[0].section_path == ("Synchronization", "Mutex")
    assert context[1].document_id == supplementary
    assert context[0].similarity == pytest.approx(context[1].similarity)
    assert context[0].score > context[1].score
    assert not_indexed not in {candidate.document_id for candidate in context}

    mandatory = retrieval.retrieve(
        query, SourceAuthorityPolicy.for_purpose(EvidencePurpose.MANDATORY), 5
    )
    assert supplementary not in {candidate.document_id for candidate in mandatory}

    filtered = retrieval.retrieve(
        RetrievalQuery(course_id="sop", text="mutex", document_type="lab_task"),
        SourceAuthorityPolicy.for_purpose(EvidencePurpose.CONTEXT),
        5,
    )
    assert {candidate.document_id for candidate in filtered} == {pipes}

    unknown_course = RetrievalQuery(course_id="other", text="mutex")
    context_policy = SourceAuthorityPolicy.for_purpose(EvidencePurpose.CONTEXT)
    assert not retrieval.retrieve(unknown_course, context_policy, 5)


def test_vectors_without_fragments_are_not_returned(queued_env: AppEnvironment) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, MUTEX)
    ingestion, retrieval = _services(queued_env)
    ingestion.ingest(document_id)
    queued_env.container.documents.replace_chunks(document_id, [])

    evidence = retrieval.retrieve(
        RetrievalQuery(course_id="sop", text="mutex"),
        SourceAuthorityPolicy.for_purpose(EvidencePurpose.CONTEXT),
        5,
    )
    assert not evidence


def test_retrieval_service_serialises_evidence(queued_env: AppEnvironment) -> None:
    user, _ = queued_env.add_user(UserRole.INSTRUCTOR)
    document_id = _upload(queued_env, user, MUTEX)
    ingestion, retrieval = _services(queued_env)
    ingestion.ingest(document_id)

    result = RetrievalService(retrieval, "hashing-bow-256").run(
        "sop", {"query": "barrier threads wait", "top_k": 1, "purpose": "mandatory"}
    )
    assert result["strategy"] == "vector"
    assert result["purpose"] == "mandatory"
    assert len(result["evidence"]) == 1
    evidence = result["evidence"][0]
    assert evidence["section_path"] == ["Synchronization", "Barrier"]
    assert evidence["document_id"] == str(document_id)
    assert evidence["filename"] == "notes.md"
    assert all(
        isinstance(value, (str, int, float, list, type(None)))
        for value in evidence.values()
    )
