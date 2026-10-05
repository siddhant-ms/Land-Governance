"""ObjectStore abstraction. Local-filesystem implementation (S3-compatible adapter is a drop-in)."""
import re
from pathlib import Path

from app.core.config import get_settings


class LocalObjectStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", key) or ".." in key:
            raise ValueError("invalid storage key")
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("path escapes storage root")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"file://{key}"

    def get(self, uri: str) -> bytes:
        return self._path(uri.removeprefix("file://")).read_bytes()


def get_store() -> LocalObjectStore:
    return LocalObjectStore(get_settings().object_storage_url)
