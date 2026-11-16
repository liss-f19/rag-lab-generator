"""
Role:   Abstract base for corpus sources (git clone, HTTP listing download).
Input:  Settings; destination directory at fetch time.
Output: List of SourceRef describing every file placed on disk.
Flow:   Subclasses implement fetch(); base offers sha256 helper used for manifests.
"""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from rag_lab_generator.config import Settings
from rag_lab_generator.models import SourceRef


class Source(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def fetch(self, dest: Path, force: bool = False) -> list[SourceRef]:
        """Populate dest with the source files; skip already-present files unless force."""

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
