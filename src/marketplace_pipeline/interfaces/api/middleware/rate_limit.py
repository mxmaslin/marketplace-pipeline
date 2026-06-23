from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from marketplace_pipeline.interfaces.api.middleware.public_paths import is_public_path


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit_response() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
        headers={"Retry-After": "60"},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory per-IP sliding window rate limiter."""

    def __init__(self, app: ASGIApp, *, limit_per_minute: int) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _allow(self, client_ip: str) -> bool:
        if self._limit <= 0:
            return True
        now = time.monotonic()
        window_start = now - 60.0
        hits = [ts for ts in self._hits[client_ip] if ts >= window_start]
        if len(hits) >= self._limit:
            self._hits[client_ip] = hits
            return False
        hits.append(now)
        self._hits[client_ip] = hits
        return True

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if is_public_path(request.url.path):
            return await call_next(request)
        client_ip = _client_ip(request)
        if not self._allow(client_ip):
            return _rate_limit_response()
        return await call_next(request)


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed per-IP sliding window rate limiter for multi-replica API."""

    def __init__(self, app: ASGIApp, *, limit_per_minute: int, redis_url: str) -> None:
        super().__init__(app)
        from marketplace_pipeline.infrastructure.rate_limit.redis_sliding_window import (
            RedisSlidingWindowRateLimiter,
        )

        self._limiter = RedisSlidingWindowRateLimiter(
            redis_url,
            limit_per_minute=limit_per_minute,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if is_public_path(request.url.path):
            return await call_next(request)
        client_ip = _client_ip(request)
        if not self._limiter.allow(client_ip):
            return _rate_limit_response()
        return await call_next(request)
