from datetime import timedelta
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.time import utcnow


def hash_password(password: str) -> str:
    rounds = 4 if get_settings().environment == "test" else 12
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def create_token(user_id: str, token_type: str, lifetime: timedelta) -> tuple[str, str]:
    settings = get_settings()
    jti = uuid4().hex
    now = utcnow()
    payload = {
        "sub": user_id,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError(401, "Missing or invalid authentication") from exc
