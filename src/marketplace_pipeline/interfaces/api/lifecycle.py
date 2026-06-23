from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.composition.factories import (
    build_job_finished_callback,
    build_job_idempotency_store,
    build_job_repository,
    build_job_runner,
)
from marketplace_pipeline.infrastructure.config.settings import get_settings
from marketplace_pipeline.infrastructure.logging import configure_logging
from marketplace_pipeline.infrastructure.observability.metrics import MetricsRegistry
from marketplace_pipeline.infrastructure.observability.tracing import (
    setup_opentelemetry,
    setup_sentry,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)

    if settings.sentry_dsn:
        setup_sentry(dsn=settings.sentry_dsn, environment=settings.sentry_environment)
    if settings.otel_enabled:
        setup_opentelemetry(
            app,
            service_name=settings.otel_service_name,
            otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        )

    output_dir = Container(settings).output_dir
    job_repo = build_job_repository(settings)
    metrics = MetricsRegistry(
        redis_url=settings.redis_url if settings.job_runner_backend == "celery" else None
    )
    on_job_finished = build_job_finished_callback(metrics)

    job_runner = build_job_runner(
        settings,
        job_repo,
        output_dir=output_dir,
        on_job_finished=on_job_finished,
    )
    app.state.settings = settings
    app.state.job_repository = job_repo
    app.state.job_runner = job_runner
    app.state.job_idempotency_store = build_job_idempotency_store(settings)
    app.state.metrics = metrics
    logger.info(
        "API started: job_store=%s runner=%s idempotency=%s auth=%s",
        settings.job_store_backend,
        settings.job_runner_backend,
        settings.crm_idempotency_backend,
        settings.api_auth_enabled,
    )
    yield
    job_runner.shutdown(wait=True)
    logger.info("API shutdown complete")
