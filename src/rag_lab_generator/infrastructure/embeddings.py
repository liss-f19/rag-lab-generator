"""Embedding providers for the EmbeddingClient port."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence

import openai

from rag_lab_generator.domain.errors import EmbeddingError
from rag_lab_generator.domain.ports import EmbeddingBatch

_TOKEN = re.compile(r"\w+", re.UNICODE)


class HashingEmbeddingClient:
    """Deterministic, offline bag-of-words embeddings (feature hashing).

    It needs no model service and gives identical vectors on every run, so it is
    used by the tests, the CI end-to-end trace, and offline development. It
    captures lexical overlap only, not meaning; retrieval quality is measured
    with the configured semantic model.
    """

    def __init__(self, dimensions: int = 1024) -> None:
        self._dimensions = dimensions

    @property
    def model_id(self) -> str:
        return f"hashing-bow-{self._dimensions}"

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        return EmbeddingBatch(vectors=[self._vector(text) for text in texts])

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        counts = Counter(token.lower() for token in _TOKEN.findall(text))
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self._dimensions
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return vector
        return [component / norm for component in vector]


class OpenAIEmbeddingClient:
    """OpenAI embeddings with explicit timeout and bounded retries.

    The SDK retries 429 and 5xx responses with exponential back-off up to
    max_retries times. Token usage is returned with every batch (NFR-02).
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        base_url: str | None = None,
        batch_size: int = 256,
    ) -> None:
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._model = model
        self._batch_size = batch_size

    @property
    def model_id(self) -> str:
        return f"openai-{self._model}"

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        vectors: list[list[float]] = []
        tokens = 0
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            try:
                response = self._client.embeddings.create(
                    model=self._model, input=batch
                )
            except openai.OpenAIError as exc:
                raise EmbeddingError(
                    "The embedding service request failed.",
                    details={"provider": "openai", "error": type(exc).__name__},
                ) from exc
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(list(item.embedding) for item in ordered)
            tokens += response.usage.total_tokens if response.usage else 0
        return EmbeddingBatch(vectors=vectors, token_count=tokens)
