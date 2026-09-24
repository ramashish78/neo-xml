from pathlib import Path

from fastapi import UploadFile

from app.core.access import Access
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import CATEGORY_PERMISSION
from app.repositories.base import Files
from app.services.audit_service import AuditService
from app.storage.disk import DiskStorage, sha256_hex

IMAGE_SIGNATURES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "gif": b"GIF8",
}


class FileService:
    def __init__(self, db):
        self.db = db
        self.repo = Files(db)
        self.disk = DiskStorage(get_settings().upload_root)
        self.access = Access(db)
        self.audit = AuditService(db)

    def save_generated(
        self,
        category: str,
        data: bytes,
        ext: str,
        original_name: str,
        workspace_id: str | None,
        user_id: str,
        mime_type: str,
    ) -> dict:
        relative = self.disk.save(category, ext, data)
        return self.repo.insert(
            {
                "original_name": original_name,
                "relative_path": relative,
                "mime_type": mime_type,
                "size": len(data),
                "checksum": sha256_hex(data),
                "category": category,
                "workspace_id": workspace_id,
                "created_by": user_id,
            }
        )

    def upload(
        self,
        user: dict,
        upload: UploadFile,
        category: str,
        workspace_id: str | None,
        ip: str,
    ) -> dict:
        permission = CATEGORY_PERMISSION.get(category)
        if permission is None:
            raise AppError(422, "Invalid category")
        self.access.require_permission(user, permission)
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
        original = upload.filename or "upload"
        self._assert_safe_name(original)
        ext = Path(original).suffix.lower().lstrip(".")
        data = self._read_limited(upload)
        mime = self._sniff(data, ext)
        saved = self.save_generated(category, data, ext, original, workspace_id, str(user["_id"]), mime)
        self.audit.record(str(user["_id"]), "file.upload", "file", str(saved["_id"]), ip)
        return saved

    def get_for_user(self, user: dict, file_id: str) -> dict:
        self.access.require_permission(user, "dm.read")
        doc = self.repo.get(file_id)
        if not doc:
            raise AppError(404, "Resource not found")
        workspace_id = doc.get("workspace_id")
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
        elif not self.access.is_super(user):
            raise AppError(404, "Resource not found")
        return doc

    def absolute_path(self, doc: dict):
        return self.disk.resolve(doc["relative_path"])

    def read_doc(self, doc: dict) -> bytes:
        return self.disk.read(doc["relative_path"])

    def delete_file(self, file_id: str) -> None:
        doc = self.repo.get(file_id)
        if not doc:
            return
        self.disk.delete(doc["relative_path"])
        self.repo.delete(file_id)

    def load_text_file(self, file_id: str, workspace_id: str) -> bytes:
        doc = self.repo.get(file_id)
        if not doc or doc.get("workspace_id") != workspace_id:
            raise AppError(404, "Resource not found")
        return self.read_doc(doc)

    def _read_limited(self, upload: UploadFile) -> bytes:
        limit = get_settings().max_upload_bytes
        upload.file.seek(0)
        data = upload.file.read(limit + 1)
        if len(data) > limit:
            raise AppError(422, "File exceeds maximum upload size")
        if not data:
            raise AppError(422, "File is empty")
        return data

    def _assert_safe_name(self, name: str) -> None:
        if not name or name != Path(name).name or ".." in name or "/" in name or "\\" in name:
            raise AppError(422, "Invalid file name")

    def _sniff(self, data: bytes, ext: str) -> str:
        allowed = {
            "xml",
            "xsd",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "svg",
            "pdf",
            "zip",
            "html",
            "txt",
            "json",
        }
        if ext not in allowed:
            raise AppError(422, "File extension is not allowed")
        upper = data[:200].lstrip().upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise AppError(422, "DOCTYPE and entities are not allowed")
        if ext in {"xml", "xsd", "svg"}:
            sample = data.lstrip()[:200].lower()
            if ext == "svg" and b"<svg" not in sample and not sample.startswith(b"<?xml"):
                raise AppError(422, "File content does not match extension")
            if ext != "svg" and not (sample.startswith(b"<?xml") or sample.startswith(b"<")):
                raise AppError(422, "File content does not match extension")
            return "image/svg+xml" if ext == "svg" else "application/xml"
        if ext in IMAGE_SIGNATURES and not data.startswith(IMAGE_SIGNATURES[ext]):
            raise AppError(422, "File content does not match extension")
        if ext == "pdf" and not data.startswith(b"%PDF"):
            raise AppError(422, "File content does not match extension")
        if ext == "zip" and not data.startswith(b"PK"):
            raise AppError(422, "File content does not match extension")
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "pdf": "application/pdf",
            "zip": "application/zip",
            "html": "text/html",
            "txt": "text/plain",
            "json": "application/json",
        }
        return mime[ext]
