"""
Role:   Unit tests for the HuggingFace remote bge-m3 embedder.
Input:  A mocked httpx transport returning canned vectors.
Output: none
Flow:   Builds the embedder with a MockTransport client, checks normalization, batching, pooling
        of token-level output, and the error raised on a non-200 response.
"""

import json

import httpx
import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.retrieval.embeddings.bge_m3_hf import BgeM3HFEmbedder, HFEmbeddingError


def _client(payload: object, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "inputs" in body
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_query_vector_is_normalized(settings: Settings) -> None:
    emb = BgeM3HFEmbedder(settings, client=_client([[3.0, 4.0]]))
    vec = emb.embed_query("hello")
    assert vec == pytest.approx([0.6, 0.8])


def test_token_level_output_is_pooled(settings: Settings) -> None:
    emb = BgeM3HFEmbedder(settings, client=_client([[[1.0, 0.0], [0.0, 1.0]]]))
    vec = emb.embed_query("hello")
    assert vec == pytest.approx([0.7071, 0.7071], abs=1e-3)


def test_documents_batch_and_keep_order(settings: Settings) -> None:
    emb = BgeM3HFEmbedder(settings, client=_client([[1.0, 0.0], [0.0, 2.0]]))
    vecs = emb.embed_documents(["a", "b"])
    assert vecs == [[1.0, 0.0], [0.0, 1.0]]


def test_non_200_raises(settings: Settings) -> None:
    emb = BgeM3HFEmbedder(settings, client=_client({"error": "loading"}, status=503))
    with pytest.raises(HFEmbeddingError):
        emb.embed_query("x")


def test_vectors_live_in_the_local_bge_m3_space(settings: Settings) -> None:
    emb = BgeM3HFEmbedder(settings, client=_client([[1.0, 0.0]]))
    assert emb.name == "bge_m3_hf"
    assert emb.vector_space == "bge_m3"
