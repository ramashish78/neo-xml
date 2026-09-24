from app.core.errors import AppError


class Access:
    def __init__(self, db):
        self.db = db

    def permissions_for(self, user: dict) -> set[str]:
        cached = user.get("_perm_cache")
        if cached is not None:
            return cached
        names = user.get("roles") or []
        perms: set[str] = set()
        for role in self.db.roles.find({"name": {"$in": names}}):
            perms.update(role.get("permissions") or [])
        user["_perm_cache"] = perms
        return perms

    def is_super(self, user: dict) -> bool:
        return "Super Admin" in (user.get("roles") or [])

    def can_see_workspace(self, user: dict, workspace_id: str) -> bool:
        if self.is_super(user):
            return True
        return str(workspace_id) in {str(item) for item in user.get("workspace_ids") or []}

    def require_workspace(self, user: dict, workspace_id: str) -> None:
        if not self.can_see_workspace(user, workspace_id):
            raise AppError(404, "Resource not found")

    def require_permission(self, user: dict, permission: str) -> None:
        if permission not in self.permissions_for(user):
            raise AppError(403, "Insufficient permission")
