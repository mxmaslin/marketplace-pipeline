from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from marketplace_pipeline.infrastructure.config.settings import get_settings
from marketplace_pipeline.interfaces.api.lifecycle import lifespan
from marketplace_pipeline.interfaces.api.middleware.auth import ApiKeyAuthMiddleware
from marketplace_pipeline.interfaces.api.middleware.rate_limit import (
    RateLimitMiddleware,
    RedisRateLimitMiddleware,
)
from marketplace_pipeline.interfaces.api.routes.health import router as health_router
from marketplace_pipeline.interfaces.api.routes.jobs import router as jobs_router

API_VERSION = "0.5.0"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            metrics.inc_http()
            metrics.observe_http_duration_ms(elapsed_ms)
        return response


def _configure_openapi_security(app: FastAPI, *, api_auth_enabled: bool) -> None:
    if not api_auth_enabled:
        return

    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        components = schema.setdefault("components", {})
        components["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
            },
        }
        for path, path_item in schema.get("paths", {}).items():
            if not path.startswith("/api/v1"):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"ApiKeyAuth": []}, {"BearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Marketplace Pipeline API",
        description=(
            "Production backend over Clean Architecture pipeline: "
            "async jobs, SQLite job store, auth, rate limits, health probes, OpenAPI."
        ),
        version=API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    rate_limit_kwargs = {"limit_per_minute": settings.api_rate_limit_per_minute}
    if settings.redis_url.strip():
        app.add_middleware(
            RedisRateLimitMiddleware,
            redis_url=settings.redis_url,
            **rate_limit_kwargs,
        )
    else:
        app.add_middleware(RateLimitMiddleware, **rate_limit_kwargs)
    app.add_middleware(ApiKeyAuthMiddleware, api_key=settings.api_key)
    _configure_openapi_security(app, api_auth_enabled=settings.api_auth_enabled)
    app.include_router(health_router)
    app.include_router(jobs_router, prefix="/api/v1")

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.app.state.metrics.render_prometheus())

    return app


app = create_app()
