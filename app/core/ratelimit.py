from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings


class SlidingWindowLimiter:
    """In-process sliding-window rate limiter keyed by a string identifier."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests, please try again later",
                )
            hits.append(now)

    def prune(self) -> None:
        now = time.monotonic()
        with self._lock:
            stale = [
                key
                for key, hits in self._hits.items()
                if not hits or hits[-1] <= now - self.window_seconds
            ]
            for key in stale:
                del self._hits[key]


def _client_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    limiter: SlidingWindowLimiter,
) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if get_settings().is_test:
            return
        limiter.check(_client_identifier(request))

    return dependency


login_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=300)
upload_limiter = SlidingWindowLimiter(max_requests=60, window_seconds=3600)

LoginRateLimit = Annotated[None, Depends(rate_limit(login_limiter))]
UploadRateLimit = Annotated[None, Depends(rate_limit(upload_limiter))]