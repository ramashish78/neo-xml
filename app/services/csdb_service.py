from app.core.access import Access
from app.core.errors import AppError
from app.repositories.base import DataModules, Ddn, Dmrl, Files, Graphics, PublicationModules, Workspaces
from app.services.audit_service import AuditService
from app.services.content_helpers import check_code, next_code, require_active_workspace
from app.services.data_module_service import DataModuleService
from app.services.publishing_service import PublishingService


class CsdbService:
    def __init__(self, db):
        self.db = db
        self.access = Access(db)
        self.workspaces = Workspaces(db)
        self.modules = DataModules(db)
        self.graphics = Graphics(db)
        self.publications = PublicationModules(db)
        self.files = Files(db)
        self.dmrl = Dmrl(db)
        self.ddn = Ddn(db)
        self.audit = AuditService(db)
        self.data_modules = DataModuleService(db)
        self.publishing = PublishingService(db)

    def summary(self, user: dict, workspace_id: str) -> dict:
        if not self.access.can_see_workspace(user, workspace_id):
            raise AppError(404, "Resource not found")
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            raise AppError(404, "Resource not found")
        scope = {"workspace_id": workspace_id}
        return {
            "workspace_id": workspace_id,
            "name": workspace["name"],
            "counts": {
                "data_modules": self.modules.count(scope),
                "graphics": self.graphics.count(scope),
                "publication_modules": self.publications.count(scope),
                "brex": self.files.count({**scope, "category": "brex"}),
                "dmrl": self.dmrl.count(scope),
                "ddn": self.ddn.count(scope),
            },
        }

    def create_dmrl(self, user: dict, body, ip: str) -> dict:
        require_active_workspace(self.db, user, self.access, body.workspace_id)
        for entry in body.entries:
            if not self.modules.by_dmc(body.workspace_id, entry.dmc):
                raise AppError(422, f"Unknown DMC {entry.dmc}")
        code = check_code(body.code, "DMRL code") if body.code else next_code(self.dmrl, body.workspace_id, "code", "DMRL")
        doc = self.dmrl.insert(
            {
                "workspace_id": body.workspace_id,
                "code": code,
                "title": body.title,
                "entries": [entry.model_dump() for entry in body.entries],
                "status": "active",
                "created_by": str(user["_id"]),
            },
            "Duplicate DMRL code",
        )
        self.audit.record(str(user["_id"]), "dmrl.create", "dmrl", str(doc["_id"]), ip)
        return doc

    def list_dmrl(self, user: dict, workspace_id: str | None, limit: int, skip: int):
        return self._scoped_list(self.dmrl, user, workspace_id, limit, skip)

    def get_dmrl(self, user: dict, dmrl_id: str) -> dict:
        return self._visible(self.dmrl, user, dmrl_id)

    def create_ddn(self, user: dict, body, ip: str) -> dict:
        require_active_workspace(self.db, user, self.access, body.workspace_id)
        dmrl = self.dmrl.get(body.dmrl_id)
        if not dmrl or dmrl.get("workspace_id") != body.workspace_id:
            raise AppError(404, "Resource not found")
        code = check_code(body.code, "DDN code") if body.code else next_code(self.ddn, body.workspace_id, "code", "DDN")
        doc = self.ddn.insert(
            {
                "workspace_id": body.workspace_id,
                "code": code,
                "title": body.title,
                "dmrl_id": body.dmrl_id,
                "recipient": body.recipient,
                "status": "draft",
                "created_by": str(user["_id"]),
            },
            "Duplicate DDN code",
        )
        self.audit.record(str(user["_id"]), "ddn.create", "ddn", str(doc["_id"]), ip)
        return doc

    def list_ddn(self, user: dict, workspace_id: str | None, limit: int, skip: int):
        return self._scoped_list(self.ddn, user, workspace_id, limit, skip)

    def get_ddn(self, user: dict, ddn_id: str) -> dict:
        return self._visible(self.ddn, user, ddn_id)

    def _scoped_list(self, repo, user, workspace_id, limit, skip):
        query = {}
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
            query["workspace_id"] = workspace_id
        elif not self.access.is_super(user):
            query["workspace_id"] = {"$in": [str(item) for item in user.get("workspace_ids") or []]}
        return repo.list(query, limit, skip, [("created_at", -1)])

    def _visible(self, repo, user, doc_id: str) -> dict:
        doc = repo.get(doc_id)
        if not doc:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, doc["workspace_id"])
        return doc
