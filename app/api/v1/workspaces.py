from fastapi import APIRouter, Depends, Query, Request

from app.core.db import get_db
from app.core.deps import get_current_user, require
from app.core.rate_limit import client_ip
from app.core.serialize import page, to_public
from app.schemas.dto import WorkspaceCreate, WorkspaceUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
def list_workspaces(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    items, total = UserService(db).list_workspaces(user, limit, skip)
    return page(items, total)


@router.post("", status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(UserService(db).create_workspace(user, body.name, client_ip(request)))


@router.patch("/{workspace_id}")
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(UserService(db).update_workspace(user, workspace_id, body, client_ip(request)))
