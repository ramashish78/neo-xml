from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, Header

from app.core.access import Access
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "Missing or invalid authentication")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AppError(401, "Missing or invalid authentication")
    try:
        user_id = ObjectId(payload.get("sub"))
    except (InvalidId, TypeError) as exc:
        raise AppError(401, "Missing or invalid authentication") from exc
    user = db.users.find_one({"_id": user_id})
    if not user or user.get("status") != "active":
        raise AppError(401, "Missing or invalid authentication")
    return user


def require(permission: str):
    def checker(user=Depends(get_current_user), db=Depends(get_db)):
        Access(db).require_permission(user, permission)
        return user

    return checker
