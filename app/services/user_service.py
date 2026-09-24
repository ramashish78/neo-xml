from app.core.access import Access
from app.core.errors import AppError
from app.core.security import hash_password
from app.repositories.base import Roles, Users, Workspaces
from app.services.audit_service import AuditService


class UserService:
    def __init__(self, db):
        self.db = db
        self.users = Users(db)
        self.roles = Roles(db)
        self.workspaces = Workspaces(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def create(self, actor: dict, body, ip: str) -> dict:
        self._check_roles(body.roles)
        self._check_workspaces(body.workspace_ids)
        if "Super Admin" not in body.roles and not body.workspace_ids:
            raise AppError(422, "workspace_ids is required")
        if self.users.by_email(body.email):
            raise AppError(409, "Email already exists")
        doc = self.users.insert(
            {
                "email": body.email,
                "name": body.name,
                "password_hash": hash_password(body.password),
                "roles": body.roles,
                "workspace_ids": body.workspace_ids,
                "status": "active",
            },
            "Email already exists",
        )
        self.audit.record(str(actor["_id"]), "user.create", "user", str(doc["_id"]), ip)
        return doc

    def list_users(self, limit: int, skip: int):
        return self.users.list({}, limit, skip, [("email", 1)])

    def update(self, actor: dict, user_id: str, body, ip: str) -> dict:
        current = self.users.get(user_id)
        if not current:
            raise AppError(404, "Resource not found")
        fields = {}
        if body.name is not None:
            fields["name"] = body.name
        if body.roles is not None:
            self._check_roles(body.roles)
            if "Super Admin" not in body.roles and not (body.workspace_ids or current.get("workspace_ids")):
                raise AppError(422, "workspace_ids is required")
            fields["roles"] = body.roles
        if body.workspace_ids is not None:
            self._check_workspaces(body.workspace_ids)
            fields["workspace_ids"] = body.workspace_ids
        if body.status is not None:
            fields["status"] = body.status
        roles = fields.get("roles", current.get("roles") or [])
        status = fields.get("status", current.get("status"))
        self._protect_last_admin(current, roles, status)
        updated = self.users.update(user_id, fields)
        self.audit.record(str(actor["_id"]), "user.update", "user", user_id, ip)
        return updated

    def list_roles(self, limit: int, skip: int):
        return self.roles.list({}, limit, skip, [("name", 1)])

    def create_workspace(self, actor: dict, name: str, ip: str) -> dict:
        doc = self.workspaces.insert(
            {
                "name": name,
                "status": "active",
                "schema_file_id": None,
                "brex_file_id": None,
                "ste_file_id": None,
            },
            "Workspace name already exists",
        )
        self.audit.record(str(actor["_id"]), "workspace.create", "workspace", str(doc["_id"]), ip)
        return doc

    def list_workspaces(self, user: dict, limit: int, skip: int):
        query = {}
        if not self.access.is_super(user):
            query["_id"] = {"$in": _oids(user.get("workspace_ids") or [])}
        return self.workspaces.list(query, limit, skip, [("name", 1)])

    def update_workspace(self, actor: dict, workspace_id: str, body, ip: str) -> dict:
        current = self.workspaces.get(workspace_id)
        if not current:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(actor, workspace_id)
        fields = {}
        if body.name is not None:
            fields["name"] = body.name
        if body.status is not None:
            fields["status"] = body.status
        for key in ("schema_file_id", "brex_file_id", "ste_file_id"):
            value = getattr(body, key)
            if value is not None:
                fields[key] = value
        updated = self.workspaces.update(workspace_id, fields) if fields else current
        self.audit.record(str(actor["_id"]), "workspace.update", "workspace", workspace_id, ip)
        return updated

    def _check_roles(self, names: list[str]) -> None:
        found = {role["name"] for role in self.roles.by_names(names)}
        if found != set(names):
            raise AppError(422, "Unknown role")

    def _check_workspaces(self, ids: list[str]) -> None:
        for workspace_id in ids:
            workspace = self.workspaces.get(workspace_id)
            if not workspace or workspace.get("status") != "active":
                raise AppError(422, "Unknown workspace")

    def _protect_last_admin(self, current: dict, roles: list[str], status: str) -> None:
        if "Super Admin" not in (current.get("roles") or []):
            return
        if "Super Admin" in roles and status == "active":
            return
        others = self.users.col.count_documents(
            {"roles": "Super Admin", "status": "active", "_id": {"$ne": current["_id"]}}
        )
        if others == 0:
            raise AppError(409, "Cannot remove the last Super Admin")


def _oids(values: list[str]):
    from bson import ObjectId
    from bson.errors import InvalidId

    ids = []
    for value in values:
        try:
            ids.append(ObjectId(value))
        except (InvalidId, TypeError):
            continue
    return ids
