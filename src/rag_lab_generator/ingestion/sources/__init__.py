"""
Role:   Source strategies package; importing it registers every source implementation.
Input:  none
Output: none
Flow:   Imports base and each implementation module so @register decorators execute.
"""

from rag_lab_generator.ingestion.sources import kozlowski, sop_site  # noqa: F401
from rag_lab_generator.ingestion.sources.base import Source

__all__ = ["Source"]
