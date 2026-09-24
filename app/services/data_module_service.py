import difflib

from app.core.access import Access
from app.core.errors import AppError
from app.core.permissions import (
    DM_APPROVED,
    DM_AUTHOR,
    DM_DRAFT,
    FROZEN_STATUSES,
)
from app.repositories.base import DataModules, Revisions
from app.services.audit_service import AuditService
from app.services.content_helpers import (
    assert_graphics,
    check_code,
    next_code,
    require_active_workspace,
    store_xml,
    xml_from_request,
)
from app.services.file_service import FileService


class DataModuleService:
    def __init__(self, db):
        self.db = db
        self.modules = DataModules(db)
        self.revisions = Revisions(db)
        self.files = FileService(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def create(self, user: dict, body, ip: str) -> dict:
        require_active_workspace(self.db, user, self.access, body.workspace_id)
        assert_graphics(self.db, body.workspace_id, body.graphic_ids)
        dmc = check_code(body.dmc, "DMC") if body.dmc else next_code(self.modules, body.workspace_id, "dmc", "DMC")
        if self.modules.by_dmc(body.workspace_id, dmc):
            raise AppError(409, "Duplicate DMC")
        data, existing = xml_from_request(self.files, body, body.workspace_id)
        if existing:
            file_doc = existing
        else:
            file_doc = store_xml(
                self.files, "data_modules", data, f"{dmc}.xml", body.workspace_id, str(user["_id"])
            )
        module = self.modules.insert(
            {
                "workspace_id": body.workspace_id,
                "dmc": dmc,
                "title": body.title,
                "type": body.type,
                "language": body.language,
                "applicability": body.applicability,
                "status": DM_DRAFT,
                "current_revision": 1,
                "approved_revision": None,
                "file_id": str(file_doc["_id"]),
                "graphic_ids": body.graphic_ids,
                "latest_validation_id": None,
                "created_by": str(user["_id"]),
            },
            "Duplicate DMC",
        )
        self._add_revision(module, file_doc, user, 1, body.comment if hasattr(body, "comment") else None)
        self.audit.record(str(user["_id"]), "dm.create", "data_module", str(module["_id"]), ip)
        return module

    def list_modules(self, user: dict, workspace_id: str | None, status: str | None, q: str | None, limit: int, skip: int):
        query = self._scope(user, workspace_id)
        if status:
            query["status"] = status
        if q:
            query["title"] = {"$regex": __import__("re").escape(q), "$options": "i"}
        return self.modules.list(query, limit, skip, [("updated_at", -1)])

    def get(self, user: dict, module_id: str) -> dict:
        return self._visible(user, module_id)

    def patch(self, user: dict, module_id: str, body, ip: str) -> dict:
        module = self._visible(user, module_id)
        if body.xml_content:
            raise AppError(409, "Approved content is immutable; create a new revision") if module["status"] in FROZEN_STATUSES else None
        if module["status"] in FROZEN_STATUSES:
            raise AppError(409, "Approved content is immutable; create a new revision")
        fields = {}
        for key in ("title", "type", "language", "applicability"):
            value = getattr(body, key)
            if value is not None:
                fields[key] = value
        if body.graphic_ids is not None:
            assert_graphics(self.db, module["workspace_id"], body.graphic_ids)
            fields["graphic_ids"] = body.graphic_ids
        if body.xml_content:
            data = body.xml_content.encode("utf-8")
            file_doc = store_xml(
                self.files,
                "revisions",
                data,
                f"{module['dmc']}.xml",
                module["workspace_id"],
                str(user["_id"]),
            )
            revision = module["current_revision"] + 1
            self._add_revision(module, file_doc, user, revision, None)
            fields["current_revision"] = revision
            fields["file_id"] = str(file_doc["_id"])
            fields["status"] = DM_AUTHOR if module["status"] == DM_DRAFT else module["status"]
        updated = self.modules.update(module_id, fields) if fields else module
        self.audit.record(str(user["_id"]), "dm.update", "data_module", module_id, ip)
        return updated

    def delete(self, user: dict, module_id: str, ip: str) -> None:
        module = self._visible(user, module_id)
        if module["status"] in FROZEN_STATUSES:
            raise AppError(409, "Approved content cannot be deleted")
        for revision in self.revisions.for_module(module_id):
            if revision.get("file_id"):
                self.files.delete_file(revision["file_id"])
        self.revisions.delete_for_module(module_id)
        self.modules.delete(module_id)
        self.audit.record(str(user["_id"]), "dm.delete", "data_module", module_id, ip)

    def add_revision(self, user: dict, module_id: str, body, ip: str) -> dict:
        module = self._visible(user, module_id)
        require_active_workspace(self.db, user, self.access, module["workspace_id"])
        data, existing = xml_from_request(self.files, body, module["workspace_id"])
        if existing:
            file_doc = existing
        else:
            file_doc = store_xml(
                self.files, "revisions", data, f"{module['dmc']}.xml", module["workspace_id"], str(user["_id"])
            )
        revision_no = module["current_revision"] + 1
        revision = self._add_revision(module, file_doc, user, revision_no, body.comment)
        status = DM_DRAFT if module["status"] in FROZEN_STATUSES else DM_AUTHOR
        if module["status"] == DM_DRAFT:
            status = DM_AUTHOR
        self.modules.update(
            module_id,
            {
                "current_revision": revision_no,
                "file_id": str(file_doc["_id"]),
                "status": status,
            },
        )
        self.audit.record(str(user["_id"]), "dm.revise", "data_module", module_id, ip)
        return revision

    def history(self, user: dict, module_id: str) -> list:
        self._visible(user, module_id)
        return self.revisions.for_module(module_id)

    def compare(self, user: dict, module_id: str, left: int, right: int) -> dict:
        module = self._visible(user, module_id)
        left_rev = self.revisions.by_number(module_id, left)
        right_rev = self.revisions.by_number(module_id, right)
        if not left_rev or not right_rev:
            raise AppError(404, "Resource not found")
        left_text = self._xml_text(left_rev)
        right_text = self._xml_text(right_rev)
        changes = []
        matcher = difflib.SequenceMatcher(a=left_text.splitlines(), b=right_text.splitlines())
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            kind = {"replace": "modify", "delete": "delete", "insert": "insert"}[tag]
            changes.append(
                {
                    "change_type": kind,
                    "location": f"line {i1 + 1}",
                    "original_text": "\n".join(left_text.splitlines()[i1:i2]),
                    "new_text": "\n".join(right_text.splitlines()[j1:j2]),
                }
            )
        return {"data_module_id": module_id, "dmc": module["dmc"], "left": left, "right": right, "changes": changes}

    def _add_revision(self, module: dict, file_doc: dict, user: dict, number: int, comment: str | None):
        return self.revisions.insert(
            {
                "data_module_id": str(module["_id"]),
                "revision": number,
                "issue": f"{number:03d}",
                "file_id": str(file_doc["_id"]),
                "file_path": file_doc["relative_path"],
                "checksum": file_doc["checksum"],
                "author_id": str(user["_id"]),
                "comment": comment,
            }
        )

    def _visible(self, user: dict, module_id: str) -> dict:
        module = self.modules.get(module_id)
        if not module:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, module["workspace_id"])
        return module

    def _scope(self, user: dict, workspace_id: str | None) -> dict:
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
            return {"workspace_id": workspace_id}
        if self.access.is_super(user):
            return {}
        return {"workspace_id": {"$in": [str(item) for item in user.get("workspace_ids") or []]}}

    def _xml_text(self, revision: dict) -> str:
        doc = self.files.repo.get(revision["file_id"])
        if not doc:
            raise AppError(404, "Resource not found")
        return self.files.read_doc(doc).decode("utf-8", errors="replace")
