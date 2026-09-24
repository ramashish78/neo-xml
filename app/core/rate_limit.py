import time

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, list[float]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        recent = [stamp for stamp in self.hits.get(key, []) if now - stamp < window_seconds]
        if len(recent) >= limit:
            raise AppError(429, "Too many requests")
        recent.append(now)
        self.hits[key] = recent

    def reset(self) -> None:
        self.hits.clear()


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


def enforce_rate_limit(request: Request, bucket: str, limit: int, window_seconds: int = 60) -> None:
    if get_settings().environment == "test":
        return
    rate_limiter.hit(f"{bucket}:{client_ip(request)}", limit, window_seconds)
