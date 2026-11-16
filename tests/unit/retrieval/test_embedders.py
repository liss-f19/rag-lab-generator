"""
Role:   Unit tests for the deterministic fake embedder and embedder registration.
Input:  `settings` fixture (embedding_dim=64).
Output: Assertions; no side effects.
Flow:   Checks dimension, determinism, normalization and that cosine of equal texts is 1 while
        cosine of unrelated texts stays far from 1; bge_m3 is only checked for registration.
"""

import numpy as np

from rag_lab_generator import registry
from rag_lab_generator.config import Settings


def test_fake_embedder_is_deterministic(settings: Settings) -> None:
    embedder = registry.create("embedder", "fake", settings=settings)
    first = embedder.embed_documents(["readdir returns the next entry"])[0]
    second = embedder.embed_query("readdir returns the next entry")
    assert first == second
    assert len(first) == settings.embedding_dim


def test_fake_embedder_vectors_are_normalized(settings: Settings) -> None:
    embedder = registry.create("embedder", "fake", settings=settings)
    vectors = np.asarray(embedder.embed_documents(["a", "b", "c"]))
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_fake_embedder_cosine_separates_texts(settings: Settings) -> None:
    embedder = registry.create("embedder", "fake", settings=settings)
    a, b = np.asarray(embedder.embed_documents(["opendir", "opendir"]))
    c = np.asarray(embedder.embed_query("semaphore"))
    assert float(np.dot(a, b)) == 1.0
    assert abs(float(np.dot(a, c))) < 0.9


def test_embedders_are_registered() -> None:
    assert {"fake", "bge_m3"}.issubset(registry.available("embedder"))


def test_bge_m3_does_not_load_the_model_on_construction(settings: Settings) -> None:
    embedder = registry.create("embedder", "bge_m3", settings=settings)
    assert embedder.name == "bge_m3"
    assert embedder._model is None
