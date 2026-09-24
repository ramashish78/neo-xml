from app.repositories.base import AuditLogs


class AuditQueryService:
    def __init__(self, db):
        self.repo = AuditLogs(db)

    def list_logs(self, resource_type: str | None, resource_id: str | None, limit: int, skip: int):
        query = {}
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        return self.repo.list(query, limit, skip, [("timestamp", -1)])
