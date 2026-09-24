from datetime import timedelta

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_token, decode_token, hash_password, verify_password
from datetime import timezone

from app.core.time import utcnow
from app.repositories.base import RefreshTokens, Users
from app.services.audit_service import AuditService
from app.core.access import Access


class AuthService:
    def __init__(self, db):
        self.db = db
        self.users = Users(db)
        self.tokens = RefreshTokens(db)
        self.audit = AuditService(db)
        self.access = Access(db)

    def login(self, email: str, password: str, ip: str) -> dict:
        user = self.users.by_email(email)
        if not user or not verify_password(password, user.get("password_hash", "")):
            self.audit.record("anonymous", "auth.login.failure", "user", email, ip)
            raise AppError(401, "Invalid email or password")
        if user.get("status") != "active":
            raise AppError(401, "Invalid email or password")
        pair = self._issue_pair(str(user["_id"]))
        self.audit.record(str(user["_id"]), "auth.login", "user", str(user["_id"]), ip)
        return pair

    def refresh(self, refresh_token: str) -> dict:
        payload = self._refresh_payload(refresh_token)
        stored = self.tokens.by_jti(payload["jti"])
        if not stored or stored.get("revoked"):
            raise AppError(401, "Missing or invalid authentication")
        expires_at = stored.get("expires_at")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < utcnow():
                raise AppError(401, "Missing or invalid authentication")
        user = self.users.get(payload["sub"])
        if not user or user.get("status") != "active":
            raise AppError(401, "Missing or invalid authentication")
        self.tokens.revoke(payload["jti"])
        return self._issue_pair(str(user["_id"]))

    def logout(self, refresh_token: str, user: dict, ip: str) -> None:
        payload = self._refresh_payload(refresh_token)
        if payload.get("sub") != str(user["_id"]):
            raise AppError(401, "Missing or invalid authentication")
        self.tokens.revoke(payload["jti"])
        self.audit.record(str(user["_id"]), "auth.logout", "user", str(user["_id"]), ip)

    def me(self, user: dict) -> dict:
        perms = sorted(self.access.permissions_for(user))
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user["name"],
            "roles": user.get("roles") or [],
            "permissions": perms,
            "workspace_ids": user.get("workspace_ids") or [],
            "status": user["status"],
        }

    def change_password(self, user: dict, current_password: str, new_password: str, ip: str) -> None:
        if not verify_password(current_password, user.get("password_hash", "")):
            raise AppError(401, "Invalid email or password")
        self.users.update(str(user["_id"]), {"password_hash": hash_password(new_password)})
        self.tokens.revoke_all(str(user["_id"]))
        self.audit.record(str(user["_id"]), "auth.password_change", "user", str(user["_id"]), ip)

    def _issue_pair(self, user_id: str) -> dict:
        settings = get_settings()
        access, _ = create_token(user_id, "access", timedelta(minutes=settings.jwt_access_minutes))
        refresh, jti = create_token(user_id, "refresh", timedelta(days=settings.jwt_refresh_days))
        self.tokens.insert(
            {
                "jti": jti,
                "user_id": user_id,
                "expires_at": utcnow() + timedelta(days=settings.jwt_refresh_days),
                "revoked": False,
            }
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_minutes * 60,
        }

    def _refresh_payload(self, token: str) -> dict:
        payload = decode_token(token)
        if payload.get("type") != "refresh" or not payload.get("jti") or not payload.get("sub"):
            raise AppError(401, "Missing or invalid authentication")
        return payload
