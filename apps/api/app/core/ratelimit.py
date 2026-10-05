"""Small in-memory sliding-window limiter. Replace with a Redis-backed limiter when scaled out."""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def rate_limit(bucket: str, limit: int, window_s: int = 60):
    async def _dep(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        q = _hits[(bucket, ip)]
        now = time.monotonic()
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise AppError(429, "RATE_LIMITED", "Too many requests. Please slow down and retry shortly.")
        q.append(now)

    return _dep
