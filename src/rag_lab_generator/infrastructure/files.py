"""File storage on the shared volume used by the API and the worker."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

_URI_PREFIX = "file://"
_SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")


class LocalFileStorage:
    """Stores each upload under a generated name; the URI is relative to the root.

    Generated names avoid collisions and keep user-supplied file names out of the
    file system path.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, suffix: str) -> str:
        suffix = suffix if _SAFE_SUFFIX.match(suffix) else ""
        name = f"{uuid4().hex}{suffix}"
        relative = Path(name[:2]) / name
        target = self._root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(data)
        os.replace(temporary, target)
        return _URI_PREFIX + relative.as_posix()

    def read(self, uri: str) -> bytes:
        return self._path(uri).read_bytes()

    def delete(self, uri: str) -> None:
        self._path(uri).unlink(missing_ok=True)

    def _path(self, uri: str) -> Path:
        if not uri.startswith(_URI_PREFIX):
            raise ValueError(f"Unsupported storage URI: {uri}")
        path = (self._root / uri.removeprefix(_URI_PREFIX)).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Storage URI points outside the storage root: {uri}")
        return path
