from fastapi import APIRouter, Depends, Request, Response

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.schemas.dto import LoginRequest, LogoutRequest, PasswordChange, RefreshRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db=Depends(get_db)):
    enforce_rate_limit(request, "login", 10)
    return AuthService(db).login(body.email, body.password, client_ip(request))


@router.post("/refresh")
def refresh(body: RefreshRequest, db=Depends(get_db)):
    return AuthService(db).refresh(body.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: LogoutRequest, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    AuthService(db).logout(body.refresh_token, user, client_ip(request))
    return Response(status_code=204)


@router.get("/me")
def me(user=Depends(get_current_user), db=Depends(get_db)):
    return AuthService(db).me(user)


@router.post("/change-password", status_code=204)
def change_password(
    body: PasswordChange,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    AuthService(db).change_password(user, body.current_password, body.new_password, client_ip(request))
    return Response(status_code=204)
