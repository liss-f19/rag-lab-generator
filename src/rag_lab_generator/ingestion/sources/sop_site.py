"""
Role:   Source strategy that makes the hugo sources of sop.mini.pw.edu.pl available locally.
Input:  Settings (repo url, external_dir); destination directory and force flag at fetch time.
Output: SourceRef per relevant English file of the clone (labs, lectures, course info, attachments).
Flow:   Runs `git clone --depth 1` when the destination has no clone yet (or force removes it),
        then walks content/, static/files and the root regulations, keeping only files the
        corpus needs and skipping every .pl.md page.
"""

import shutil
import subprocess
from pathlib import Path

import httpx

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.sources.base import Source
from rag_lab_generator.models import SourceRef
from rag_lab_generator.registry import register

KEEP_SUFFIXES: frozenset[str] = frozenset(
    {".c", ".h", ".cpp", ".cc", ".py", ".sh", ".txt", ".pdf", ".zip", ".json", ".yml", ".yaml"}
)
SKIP_DIR_NAMES: frozenset[str] = frozenset({".git", "themes", "node_modules"})
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"
LFS_MEDIA_URL = "https://media.githubusercontent.com/media"
LFS_SUFFIXES: frozenset[str] = frozenset({".pdf", ".zip", ".png", ".jpg", ".svg"})


@register("source", "sop_site")
class SopSiteSource(Source):
    """Shallow clone of the public hugo sources of the course site."""

    name = "sop_site"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.repo_url = settings.sop_site_repo_url
        self.base_url = settings.sop_site_base_url

    def fetch(self, dest: Path, force: bool = False) -> list[SourceRef]:
        """Clone the site repository into dest and list every file the corpus consumes."""
        if force and dest.exists():
            shutil.rmtree(dest)
        if not (dest / ".git").is_dir():
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", self.repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
        self.resolve_lfs(dest)
        return self.list_files(dest)

    def resolve_lfs(self, root: Path) -> list[Path]:
        """Replace git-lfs pointer files by their real content, fetched over https."""
        pointers = [
            path
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and path.suffix.lower() in LFS_SUFFIXES
            and ".git" not in path.parts
            and path.stat().st_size < 1024
            and path.read_bytes().startswith(LFS_POINTER_PREFIX)
        ]
        if not pointers:
            return []
        owner = self.repo_url.removesuffix(".git").removeprefix("https://github.com/")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            for path in pointers:
                url = f"{LFS_MEDIA_URL}/{owner}/master/{path.relative_to(root).as_posix()}"
                response = client.get(url)
                if response.status_code == httpx.codes.OK:
                    path.write_bytes(response.content)
        return pointers

    def list_files(self, root: Path) -> list[SourceRef]:
        """Collect SourceRefs for the English pages, code files and attachments of the clone."""
        refs: list[SourceRef] = []
        for path in sorted((root / "content").rglob("*")):
            if not path.is_file() or SKIP_DIR_NAMES & set(path.parts):
                continue
            if path.name.endswith(".pl.md"):
                continue
            if not (path.name.endswith(".en.md") or path.suffix.lower() in KEEP_SUFFIXES):
                continue
            refs.append(self._ref(path, root))
        for path in sorted((root / "static" / "files").glob("*.zip")):
            refs.append(self._ref(path, root))
        for path in sorted(root.glob("regulamin-sop*-en.md")):
            refs.append(self._ref(path, root))
        return refs

    def _ref(self, path: Path, root: Path) -> SourceRef:
        relative = path.relative_to(root).as_posix()
        return SourceRef(
            url=f"{self.base_url}/{relative}",
            local_path=str(path),
            sha256=self.sha256(path),
        )
