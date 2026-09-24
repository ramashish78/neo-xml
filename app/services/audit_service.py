from app.core.time import utcnow
from app.repositories.base import AuditLogs


class AuditService:
    def __init__(self, db):
        self.repo = AuditLogs(db)

    def record(self, actor_id: str, action: str, resource_type: str, resource_id: str, ip: str) -> None:
        self.repo.insert(
            {
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "ip": ip,
                "timestamp": utcnow(),
            }
        )
