from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from marketplace_pipeline.infrastructure.config.settings import get_settings
from marketplace_pipeline.interfaces.api.lifecycle import lifespan
from marketplace_pipeline.interfaces.api.middleware.auth import ApiKeyAuthMiddleware
from marketplace_pipeline.interfaces.api.middleware.rate_limit import RateLimitMiddleware
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
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.api_rate_limit_per_minute)
    app.add_middleware(ApiKeyAuthMiddleware, api_key=settings.api_key)
    app.include_router(health_router)
    app.include_router(jobs_router, prefix="/api/v1")

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.app.state.metrics.render_prometheus())

    return app


app = create_app()
