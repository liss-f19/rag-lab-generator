"""
Role:   Chunking strategies package; importing it registers every chunker.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.ingestion.chunking.base import Chunker
from rag_lab_generator.ingestion.chunking.fixed import FixedChunker
from rag_lab_generator.ingestion.chunking.hierarchical import HierarchicalChunker
from rag_lab_generator.ingestion.chunking.semantic import SemanticChunker

__all__ = ["Chunker", "FixedChunker", "HierarchicalChunker", "SemanticChunker"]
