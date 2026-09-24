from pathlib import Path

from app.core.access import Access
from app.core.errors import AppError
from app.repositories.base import GraphicRevisions, Graphics
from app.services.audit_service import AuditService
from app.services.content_helpers import check_code, next_code, require_active_workspace
from app.services.file_service import FileService


class GraphicService:
    def __init__(self, db):
        self.db = db
        self.graphics = Graphics(db)
        self.history = GraphicRevisions(db)
        self.files = FileService(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def create(self, user: dict, workspace_id: str, title: str, applicability: str | None, icn: str | None, upload, ip: str):
        require_active_workspace(self.db, user, self.access, workspace_id)
        code = check_code(icn, "ICN") if icn else next_code(self.graphics, workspace_id, "icn", "ICN")
        if self.graphics.col.find_one({"workspace_id": workspace_id, "icn": code}):
            raise AppError(409, "Duplicate ICN")
        file_doc = self.files.upload(user, upload, "graphics", workspace_id, ip)
        graphic = self.graphics.insert(
            {
                "workspace_id": workspace_id,
                "icn": code,
                "title": title,
                "revision": 1,
                "file_id": str(file_doc["_id"]),
                "file_path": file_doc["relative_path"],
                "checksum": file_doc["checksum"],
                "format": Path(file_doc["original_name"]).suffix.lower().lstrip("."),
                "applicability": applicability,
                "status": "current",
                "created_by": str(user["_id"]),
            },
            "Duplicate ICN",
        )
        self.audit.record(str(user["_id"]), "graphic.upload", "graphic", str(graphic["_id"]), ip)
        return graphic

    def list_graphics(self, user: dict, workspace_id: str | None, limit: int, skip: int):
        query = {}
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
            query["workspace_id"] = workspace_id
        elif not self.access.is_super(user):
            query["workspace_id"] = {"$in": [str(item) for item in user.get("workspace_ids") or []]}
        return self.graphics.list(query, limit, skip, [("updated_at", -1)])

    def revise(self, user: dict, graphic_id: str, upload, ip: str) -> dict:
        graphic = self.graphics.get(graphic_id)
        if not graphic:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, graphic["workspace_id"])
        require_active_workspace(self.db, user, self.access, graphic["workspace_id"])
        old = {
            "graphic_id": str(graphic["_id"]),
            "icn": graphic["icn"],
            "revision": graphic["revision"],
            "file_id": graphic["file_id"],
            "file_path": graphic["file_path"],
            "checksum": graphic["checksum"],
            "author_id": graphic.get("created_by"),
            "status": "superseded",
        }
        self.history.insert(old, "Duplicate graphic revision")
        file_doc = self.files.upload(user, upload, "graphics", graphic["workspace_id"], ip)
        number = graphic["revision"] + 1
        updated = self.graphics.update(
            graphic_id,
            {
                "revision": number,
                "file_id": str(file_doc["_id"]),
                "file_path": file_doc["relative_path"],
                "checksum": file_doc["checksum"],
                "format": Path(file_doc["original_name"]).suffix.lower().lstrip("."),
                "status": "current",
            },
        )
        self.audit.record(str(user["_id"]), "graphic.revise", "graphic", graphic_id, ip)
        return updated
