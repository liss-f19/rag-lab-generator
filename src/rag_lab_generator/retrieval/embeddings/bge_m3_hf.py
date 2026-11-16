"""
Role:   Remote bge-m3 embedder using the HuggingFace Inference API; same vectors as the local
        sentence-transformers model, no torch dependency (used by the Vercel deployment).
Input:  Settings (embedding_model, embedding_dim, hf_api_token); texts at call time.
Output: L2-normalized vectors of settings.embedding_dim.
Flow:   POSTs texts in small batches to the feature-extraction pipeline endpoint with httpx,
        normalizes the returned vectors with numpy and returns plain float lists.
"""

import httpx
import numpy as np

from rag_lab_generator.config import Settings
from rag_lab_generator.registry import register
from rag_lab_generator.retrieval.embeddings.base import Embedder

HF_ENDPOINT = (
    "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
)
BATCH = 16
TIMEOUT_S = 60.0


class HFEmbeddingError(RuntimeError):
    pass


@register("embedder", "bge_m3_hf")
class BgeM3HFEmbedder(Embedder):
    name = "bge_m3_hf"
    space = "bge_m3"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        super().__init__(settings)
        self._client = client
        self._url = HF_ENDPOINT.format(model=settings.embedding_model)

    @property
    def dim(self) -> int:
        return self.settings.embedding_dim

    def _http(self) -> httpx.Client:
        if self._client is None:
            token = self.settings.hf_api_token
            headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token else {}
            self._client = httpx.Client(headers=headers, timeout=TIMEOUT_S)
        return self._client

    def _call(self, texts: list[str]) -> list[list[float]]:
        response = self._http().post(self._url, json={"inputs": texts, "normalize": True})
        if response.status_code != 200:
            raise HFEmbeddingError(f"HF inference {response.status_code}: {response.text[:200]}")
        matrix = np.asarray(response.json(), dtype=np.float32)
        # Pool token-level output to one vector per text if the endpoint returns 3-D data.
        if matrix.ndim == 3:
            matrix = matrix.mean(axis=1)
        if matrix.ndim == 1:
            matrix = matrix[None, :]
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized: list[list[float]] = (matrix / norms).tolist()
        return normalized

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            vectors.extend(self._call(texts[start : start + BATCH]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._call([text])[0]
