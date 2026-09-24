from fastapi import APIRouter, Depends, Query, Request

from app.core.db import get_db
from app.core.deps import require
from app.core.rate_limit import client_ip
from app.core.serialize import page, to_public
from app.schemas.dto import UserCreate, UserUpdate
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.get("/users")
def list_users(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    _user=Depends(require("user.read")),
    db=Depends(get_db),
):
    items, total = UserService(db).list_users(limit, skip)
    return page(items, total)


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    request: Request,
    user=Depends(require("user.manage")),
    db=Depends(get_db),
):
    return to_public(UserService(db).create(user, body, client_ip(request)))


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    user=Depends(require("user.manage")),
    db=Depends(get_db),
):
    return to_public(UserService(db).update(user, user_id, body, client_ip(request)))


@router.get("/roles")
def list_roles(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    _user=Depends(require("user.read")),
    db=Depends(get_db),
):
    items, total = UserService(db).list_roles(limit, skip)
    return page(items, total)
