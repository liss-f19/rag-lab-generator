"""
Role:   Source strategy downloading the UNIX and TCP/IP course materials of M. Kozlowski.
Input:  Settings (base url, external_dir); destination directory and force flag at fetch time.
Output: SourceRef per downloaded file under <dest>/unix and <dest>/tcpip.
Flow:   Fetches the two Apache directory listings with httpx, parses the <a href> entries,
        keeps the wanted file names per directory and downloads the missing ones; already
        present files are reused unless force is set.
"""

import re
from pathlib import Path

import httpx

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.sources.base import Source
from rag_lab_generator.models import SourceRef
from rag_lab_generator.registry import register

HREF_RE = re.compile(r'<a\s+href="([^"?/][^"]*)"', re.I)
UNIX_SUFFIXES: frozenset[str] = frozenset({".pdf", ".sh", ".txt"})
TCPIP_NAME_RE = re.compile(r"^(lecture|lab)_\d+\.pdf$")


@register("source", "kozlowski")
class KozlowskiSource(Source):
    """External lecture material published as plain Apache directory listings."""

    name = "kozlowski"
    directories: tuple[str, ...] = ("unix", "tcpip")

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.base_url = settings.kozlowski_base_url.rstrip("/")

    def fetch(self, dest: Path, force: bool = False) -> list[SourceRef]:
        """Download every wanted file of both directories into dest/<directory>/."""
        refs: list[SourceRef] = []
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            for directory in self.directories:
                listing_url = f"{self.base_url}/{directory}/"
                names = self.wanted_names(directory, client.get(listing_url).text)
                target_dir = dest / directory
                target_dir.mkdir(parents=True, exist_ok=True)
                for name in names:
                    target = target_dir / name
                    if force or not target.is_file() or target.stat().st_size == 0:
                        response = client.get(listing_url + name)
                        response.raise_for_status()
                        target.write_bytes(response.content)
                    refs.append(
                        SourceRef(
                            url=listing_url + name,
                            local_path=str(target),
                            sha256=self.sha256(target),
                        )
                    )
        return refs

    @staticmethod
    def parse_listing(html: str) -> list[str]:
        """Extract the file names of an Apache directory listing page."""
        return [name for name in HREF_RE.findall(html) if not name.endswith("/")]

    @classmethod
    def wanted_names(cls, directory: str, html: str) -> list[str]:
        """Filter a listing down to the files the corpus keeps for that directory."""
        names = cls.parse_listing(html)
        if directory == "unix":
            return sorted(n for n in names if Path(n).suffix.lower() in UNIX_SUFFIXES)
        return sorted(n for n in names if TCPIP_NAME_RE.match(n))
