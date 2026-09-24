import hashlib
from pathlib import Path
from uuid import uuid4

from app.core.errors import AppError
from app.core.permissions import UPLOAD_CATEGORIES


class DiskStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        if not relative or relative.startswith(("/", "\\")) or "\\" in relative or ".." in relative.split("/"):
            raise AppError(422, "Invalid path")
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise AppError(422, "Invalid path")
        return target

    def save(self, category: str, ext: str, data: bytes) -> str:
        if category not in UPLOAD_CATEGORIES:
            raise AppError(422, "Invalid category")
        if not ext.isascii() or not ext.isalnum() or ext != ext.lower():
            raise AppError(422, "Invalid extension")
        relative = f"{category}/{uuid4().hex}.{ext}"
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative

    def read(self, relative: str) -> bytes:
        path = self.resolve(relative)
        if not path.is_file():
            raise AppError(404, "Resource not found")
        return path.read_bytes()

    def delete(self, relative: str) -> None:
        path = self.resolve(relative)
        if path.is_file():
            path.unlink()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
