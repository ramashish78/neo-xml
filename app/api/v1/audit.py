from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.core.deps import require
from app.core.serialize import page
from app.services.audit_query import AuditQueryService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    _user=Depends(require("audit.read")),
    db=Depends(get_db),
):
    items, total = AuditQueryService(db).list_logs(resource_type, resource_id, limit, skip)
    return page(items, total)
