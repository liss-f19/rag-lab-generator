"""
Role:   RAG strategies package; importing it registers every RAG implementation.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.retrieval.rag.base import RAG
from rag_lab_generator.retrieval.rag.graph_rag import GraphRAG
from rag_lab_generator.retrieval.rag.vector_rag import VectorRAG

__all__ = ["RAG", "GraphRAG", "VectorRAG"]
