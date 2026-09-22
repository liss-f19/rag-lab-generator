"""
Role:   LLM provider strategies package; importing it registers every provider.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.generation.llm import anthropic, fake  # noqa: F401
from rag_lab_generator.generation.llm.base import LLM

__all__ = ["LLM"]
