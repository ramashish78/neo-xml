from app.core.access import Access
from app.core.errors import AppError
from app.core.permissions import DM_AUTHOR, DM_DRAFT, DM_VALIDATE
from app.repositories.base import DataModules, Files, Graphics, ValidationResults, Workspaces
from app.services.audit_service import AuditService
from app.services.file_service import FileService
from app.validation.engine import default_brex_bytes, default_schema_bytes, run_validation


class ValidationService:
    def __init__(self, db):
        self.db = db
        self.modules = DataModules(db)
        self.results = ValidationResults(db)
        self.files = FileService(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def validate_module(self, user: dict, module_id: str, ip: str) -> dict:
        module = self.modules.get(module_id)
        if not module:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, module["workspace_id"])
        xml_doc = self.files.repo.get(module["file_id"])
        if not xml_doc:
            raise AppError(404, "Resource not found")
        xml_bytes = self.files.read_doc(xml_doc)
        workspace = Workspaces(self.db).get(module["workspace_id"])
        schema = self._optional_bytes(workspace, "schema_file_id") or default_schema_bytes()
        brex = self._optional_bytes(workspace, "brex_file_id") or default_brex_bytes()
        ste = self._ste_words(workspace)
        icns = {
            item["icn"]
            for item in Graphics(self.db).col.find({"workspace_id": module["workspace_id"]}, {"icn": 1})
        }
        outcome = run_validation(xml_bytes, schema, brex, ste, icns)
        record = self.results.insert(
            {
                "object_id": module_id,
                "object_type": "data_module",
                "workspace_id": module["workspace_id"],
                "checks": outcome["checks"],
                "errors": outcome["errors"],
                "warnings": outcome["warnings"],
                "status": outcome["status"],
                "created_by": str(user["_id"]),
            }
        )
        if module["status"] in {DM_DRAFT, DM_AUTHOR, DM_VALIDATE}:
            self.modules.update(
                module_id,
                {
                    "status": DM_VALIDATE if outcome["status"] == "passed" else DM_AUTHOR,
                    "latest_validation_id": str(record["_id"]),
                },
            )
        else:
            self.modules.update(module_id, {"latest_validation_id": str(record["_id"])})
        self.audit.record(str(user["_id"]), "validation.run", "data_module", module_id, ip)
        return record

    def get_result(self, user: dict, result_id: str) -> dict:
        record = self.results.get(result_id)
        if not record:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, record["workspace_id"])
        return record

    def _optional_bytes(self, workspace: dict | None, field: str) -> bytes | None:
        if not workspace or not workspace.get(field):
            return None
        doc = Files(self.db).get(workspace[field])
        if not doc:
            return None
        return self.files.read_doc(doc)

    def _ste_words(self, workspace: dict | None) -> list[str] | None:
        if not workspace or not workspace.get("ste_file_id"):
            return None
        doc = Files(self.db).get(workspace["ste_file_id"])
        if not doc:
            return None
        text = self.files.read_doc(doc).decode("utf-8", errors="replace")
        return [line.strip() for line in text.splitlines() if line.strip()]
