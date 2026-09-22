"""
Role:   Embedding strategies package; importing it registers every embedder.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.retrieval.embeddings.base import Embedder
from rag_lab_generator.retrieval.embeddings.bge_m3 import BgeM3Embedder
from rag_lab_generator.retrieval.embeddings.bge_m3_hf import BgeM3HFEmbedder
from rag_lab_generator.retrieval.embeddings.fake import FakeEmbedder

__all__ = ["Embedder", "BgeM3Embedder", "BgeM3HFEmbedder", "FakeEmbedder"]
