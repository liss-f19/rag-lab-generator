import math
from types import SimpleNamespace

import openai
import pytest

from rag_lab_generator.domain.errors import EmbeddingError
from rag_lab_generator.domain.models import KnowledgeBaseRole, vector_collection_name
from rag_lab_generator.domain.policy import EvidencePurpose, SourceAuthorityPolicy
from rag_lab_generator.infrastructure.embeddings import (
    HashingEmbeddingClient,
    OpenAIEmbeddingClient,
)


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_hashing_embeddings_are_deterministic_and_normalised() -> None:
    client = HashingEmbeddingClient(dimensions=128)
    first, again, empty = client.embed(
        ["mutex lock unlock", "mutex lock unlock", ""]
    ).vectors
    assert first == again
    assert len(first) == 128
    assert math.isclose(sum(value * value for value in first), 1.0)
    assert not any(empty)
    assert client.model_id == "hashing-bow-128"


def test_hashing_embeddings_reflect_lexical_overlap() -> None:
    client = HashingEmbeddingClient()
    query, related, unrelated = client.embed(
        [
            "protect the critical section with a mutex",
            "a mutex protects a critical section from concurrent threads",
            "the pipe transfers bytes between processes",
        ]
    ).vectors
    assert _cosine(query, related) > _cosine(query, unrelated)


class _FakeEmbeddings:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail

    def create(self, *, model: str, input: list[str]):  # pylint: disable=redefined-builtin
        del model
        self.calls.append(input)
        if self.fail:
            raise openai.APIConnectionError(request=None)  # type: ignore[arg-type]
        data = [
            SimpleNamespace(index=position, embedding=[float(len(text)), 1.0])
            for position, text in reversed(list(enumerate(input)))
        ]
        return SimpleNamespace(
            data=data, usage=SimpleNamespace(total_tokens=len(input) * 3)
        )


def _openai_client(fake: _FakeEmbeddings, batch_size: int) -> OpenAIEmbeddingClient:
    client = OpenAIEmbeddingClient(
        api_key="sk-test",
        model="text-embedding-3-small",
        timeout_seconds=5,
        max_retries=0,
        batch_size=batch_size,
    )
    client._client = SimpleNamespace(embeddings=fake)  # pylint: disable=protected-access
    return client


def test_openai_client_batches_orders_results_and_counts_tokens() -> None:
    fake = _FakeEmbeddings()
    client = _openai_client(fake, batch_size=2)
    batch = client.embed(["a", "bb", "ccc"])
    assert fake.calls == [["a", "bb"], ["ccc"]]
    assert batch.vectors == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]
    assert batch.token_count == 9
    assert client.model_id == "openai-text-embedding-3-small"


def test_openai_failures_become_embedding_errors() -> None:
    with pytest.raises(EmbeddingError) as error:
        _openai_client(_FakeEmbeddings(fail=True), batch_size=8).embed(["a"])
    assert error.value.details["provider"] == "openai"


def test_mandatory_evidence_comes_from_the_primary_base_only() -> None:
    policy = SourceAuthorityPolicy.for_purpose(EvidencePurpose.MANDATORY)
    assert policy.admits(KnowledgeBaseRole.PRIMARY)
    assert not policy.admits(KnowledgeBaseRole.SUPPLEMENTARY)


def test_supplementary_context_ranks_below_equally_similar_primary_evidence() -> None:
    policy = SourceAuthorityPolicy.for_purpose(EvidencePurpose.CONTEXT)
    assert policy.admits(KnowledgeBaseRole.SUPPLEMENTARY)
    primary = policy.rank_score(0.80, KnowledgeBaseRole.PRIMARY)
    supplementary = policy.rank_score(0.82, KnowledgeBaseRole.SUPPLEMENTARY)
    assert primary > supplementary


@pytest.mark.parametrize(
    ("course", "model", "expected"),
    [
        (
            "operating-systems",
            "openai-text-embedding-3-small",
            "operating-systems--openai-text-embedding-3-small",
        ),
        ("sop 1/2", "hashing-bow-1024", "sop-1-2--hashing-bow-1024"),
        ("-", "-", "col--x"),
    ],
)
def test_vector_collection_names_are_valid_for_chroma(
    course: str, model: str, expected: str
) -> None:
    assert vector_collection_name(course, model) == expected
