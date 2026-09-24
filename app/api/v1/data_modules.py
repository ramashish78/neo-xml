from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.db import get_db
from app.core.deps import require
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.serialize import page, to_public
from app.schemas.dto import DataModuleCreate, DataModulePatch, RevisionCreate
from app.services.data_module_service import DataModuleService
from app.services.validation_service import ValidationService

router = APIRouter(prefix="/data-modules", tags=["data-modules"])


@router.get("")
def list_data_modules(
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


@router.post("", status_code=201)
def create_data_module(
    body: DataModuleCreate,
    request: Request,
    user=Depends(require("dm.create")),
    db=Depends(get_db),
):
    return to_public(DataModuleService(db).create(user, body, client_ip(request)))


@router.get("/{module_id}")
def get_data_module(module_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(DataModuleService(db).get(user, module_id))


@router.patch("/{module_id}")
def patch_data_module(
    module_id: str,
    body: DataModulePatch,
    request: Request,
    user=Depends(require("dm.update")),
    db=Depends(get_db),
):
    return to_public(DataModuleService(db).patch(user, module_id, body, client_ip(request)))


@router.delete("/{module_id}", status_code=204)
def delete_data_module(
    module_id: str,
    request: Request,
    user=Depends(require("dm.delete")),
    db=Depends(get_db),
):
    DataModuleService(db).delete(user, module_id, client_ip(request))
    return Response(status_code=204)


@router.post("/{module_id}/revisions", status_code=201)
def add_revision(
    module_id: str,
    body: RevisionCreate,
    request: Request,
    user=Depends(require("dm.revise")),
    db=Depends(get_db),
):
    return to_public(DataModuleService(db).add_revision(user, module_id, body, client_ip(request)))


@router.get("/{module_id}/history")
def history(module_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return [to_public(item) for item in DataModuleService(db).history(user, module_id)]


@router.get("/{module_id}/compare")
def compare(
    module_id: str,
    left: int = Query(..., ge=1),
    right: int = Query(..., ge=1),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    return DataModuleService(db).compare(user, module_id, left, right)


@router.post("/{module_id}/validate")
def validate_module(
    module_id: str,
    request: Request,
    user=Depends(require("validation.run")),
    db=Depends(get_db),
):
    enforce_rate_limit(request, "validate", 20)
    return to_public(ValidationService(db).validate_module(user, module_id, client_ip(request)))
