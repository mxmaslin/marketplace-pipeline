from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from marketplace_pipeline.interfaces.api.middleware.public_paths import is_public_path


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key or Bearer token when API_KEY is configured."""

    def __init__(self, app: ASGIApp, *, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._api_key:
            return await call_next(request)

        if is_public_path(request.url.path):
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not provided:
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip()

        if not provided or not secrets.compare_digest(provided, self._api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)
