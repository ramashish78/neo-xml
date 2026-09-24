from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.core.deps import require
from app.core.serialize import page, to_public
from app.services.csdb_service import CsdbService
from app.services.data_module_service import DataModuleService
from app.services.publishing_service import PublishingService

router = APIRouter(prefix="/csdb", tags=["csdb"])


@router.get("")
def csdb_summary(workspace_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return CsdbService(db).summary(user, workspace_id)


@router.get("/data-modules")
def csdb_data_modules(
    workspace_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = DataModuleService(db).list_modules(user, workspace_id, status, q, limit, skip)
    return page(items, total)


@router.get("/publication-modules")
def csdb_publications(
    workspace_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = PublishingService(db).list_publications(user, workspace_id, limit, skip)
    return page(items, total)
