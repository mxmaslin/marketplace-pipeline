from __future__ import annotations

import logging
from pathlib import Path

from marketplace_pipeline.domain.ports.enriched_product_repository import (
    EnrichedProductRepositoryPort,
)
from marketplace_pipeline.domain.ports.idempotency_store import IdempotencyStorePort
from marketplace_pipeline.domain.ports.job_idempotency_store import JobIdempotencyStorePort
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.domain.ports.job_runner import JobRunnerPort
from marketplace_pipeline.infrastructure.adapters.crm.file_idempotency_store import (
    FileIdempotencyStore,
)
from marketplace_pipeline.infrastructure.adapters.persistence import (
    json_enriched_product_repository,
    memory_job_idempotency_store,
)
from marketplace_pipeline.infrastructure.adapters.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.services.pipeline_job_executor import JobFinishedCallback
from marketplace_pipeline.infrastructure.services.pipeline_job_runner import PipelineJobRunner

logger = logging.getLogger(__name__)


def build_job_repository(settings: Settings) -> JobRepositoryPort:
    if settings.job_store_backend == "postgres":
        from marketplace_pipeline.infrastructure.adapters.persistence import (
            postgres_job_repository,
        )

        return postgres_job_repository.PostgresJobRepository(settings.database_url)
    return SqliteJobRepository(Path(settings.job_db_path))


def build_enriched_product_repository(
    settings: Settings,
    output_dir: Path,
) -> EnrichedProductRepositoryPort:
    if settings.job_store_backend == "postgres":
        from marketplace_pipeline.infrastructure.adapters.persistence import (
            postgres_enriched_product_repository,
        )

        return postgres_enriched_product_repository.PostgresEnrichedProductRepository(
            settings.database_url
        )
    return json_enriched_product_repository.JsonEnrichedProductRepository(output_dir)


def build_job_idempotency_store(settings: Settings) -> JobIdempotencyStorePort:
    if settings.redis_url.strip():
        from marketplace_pipeline.infrastructure.adapters.persistence import (
            redis_job_idempotency_store,
        )

        return redis_job_idempotency_store.RedisJobIdempotencyStore(
            settings.redis_url,
            ttl_seconds=settings.job_idempotency_ttl_seconds,
        )
    return memory_job_idempotency_store.MemoryJobIdempotencyStore(
        ttl_seconds=settings.job_idempotency_ttl_seconds,
    )


def build_idempotency_store(
    settings: Settings,
    output_dir: Path,
    *,
    store_path: Path | None = None,
) -> IdempotencyStorePort:
    if settings.crm_idempotency_backend == "redis":
        from marketplace_pipeline.infrastructure.adapters.crm.redis_idempotency_store import (
            RedisIdempotencyStore,
        )

        return RedisIdempotencyStore(
            settings.redis_url,
            enabled=settings.crm_idempotency_enabled,
        )
    return FileIdempotencyStore(
        store_path or Path(settings.crm_idempotency_store_path),
        enabled=settings.crm_idempotency_enabled,
    )


def build_job_runner(
    settings: Settings,
    job_repository: JobRepositoryPort,
    *,
    output_dir: Path,
    on_job_finished: JobFinishedCallback | None = None,
) -> JobRunnerPort:
    if settings.job_runner_backend == "celery":
        from marketplace_pipeline.infrastructure.services.celery_job_runner import CeleryJobRunner

        return CeleryJobRunner(settings, job_repository, output_dir=output_dir)
    return PipelineJobRunner(
        settings,
        job_repository,
        output_dir=output_dir,
        max_workers=settings.api_job_workers,
        on_job_finished=on_job_finished,
    )


def build_job_finished_callback(
    metrics: object,
) -> JobFinishedCallback:
    from marketplace_pipeline.infrastructure.observability.metrics import MetricsRegistry

    registry = metrics if isinstance(metrics, MetricsRegistry) else MetricsRegistry()

    def on_job_finished(*, success: bool, duration_seconds: float) -> None:
        registry.observe_job_duration_seconds(duration_seconds)
        if success:
            registry.inc_completed()
        else:
            registry.inc_failed()

    return on_job_finished


def ping_redis(redis_url: str) -> bool:
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=2)
        return bool(client.ping())
    except Exception as exc:
        logger.warning("Redis ping failed: %s", exc)
        return False
