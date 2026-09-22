"""
Role:   Searcher strategies package; importing it registers every searcher.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.retrieval.searchers.base import Searcher
from rag_lab_generator.retrieval.searchers.dense import DenseSearcher
from rag_lab_generator.retrieval.searchers.graph_walk import GraphWalkSearcher
from rag_lab_generator.retrieval.searchers.hybrid_rrf import (
    HybridRRFIdfSearcher,
    HybridRRFSearcher,
)
from rag_lab_generator.retrieval.searchers.lexical import LexicalSearcher
from rag_lab_generator.retrieval.searchers.lexical_idf import LexicalIdfSearcher

__all__ = [
    "Searcher",
    "DenseSearcher",
    "GraphWalkSearcher",
    "HybridRRFIdfSearcher",
    "HybridRRFSearcher",
    "LexicalIdfSearcher",
    "LexicalSearcher",
]
