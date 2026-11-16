"""Source-authority policy (FR-12, FR-13)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_lab_generator.domain.models import KnowledgeBaseRole


class EvidencePurpose(StrEnum):
    """What the retrieved evidence will be used for."""

    MANDATORY = "mandatory"
    """Mandatory requirements, course tools, learning outcomes, assessment criteria."""

    CONTEXT = "context"
    """Prerequisites, explanations, hints, and optional extensions."""


@dataclass(frozen=True)
class SourceAuthorityPolicy:
    """Which knowledge bases may supply evidence and how they are ranked.

    The primary knowledge base is authoritative. Supplementary fragments are
    excluded from mandatory evidence; for context they are allowed but rank below
    a primary fragment of similar similarity, so they cannot displace it.
    """

    allowed: frozenset[KnowledgeBaseRole]
    supplementary_penalty: float = 0.05

    @classmethod
    def for_purpose(cls, purpose: EvidencePurpose) -> SourceAuthorityPolicy:
        if purpose is EvidencePurpose.MANDATORY:
            return cls(allowed=frozenset({KnowledgeBaseRole.PRIMARY}))
        return cls(allowed=frozenset(KnowledgeBaseRole))

    def admits(self, knowledge_base: KnowledgeBaseRole) -> bool:
        return knowledge_base in self.allowed

    def rank_score(self, similarity: float, knowledge_base: KnowledgeBaseRole) -> float:
        if knowledge_base is KnowledgeBaseRole.SUPPLEMENTARY:
            return similarity - self.supplementary_penalty
        return similarity
