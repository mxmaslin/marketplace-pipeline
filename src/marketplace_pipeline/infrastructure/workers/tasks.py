from __future__ import annotations

from pathlib import Path

from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.composition.factories import (
    build_job_finished_callback,
    build_job_repository,
)
from marketplace_pipeline.infrastructure.config.settings import get_settings
from marketplace_pipeline.infrastructure.logging import configure_logging
from marketplace_pipeline.infrastructure.services.pipeline_job_executor import execute_pipeline_job
from marketplace_pipeline.infrastructure.workers.celery_app import celery_app
from marketplace_pipeline.interfaces.api.metrics import MetricsRegistry


@celery_app.task(name="pipeline.execute_job")
def execute_pipeline_job_task(job_id: str) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    job_repository = build_job_repository(settings)
    output_dir = Container(settings).output_dir
    metrics = MetricsRegistry(redis_url=settings.redis_url or None)
    execute_pipeline_job(
        settings=settings,
        job_repository=job_repository,
        job_id=job_id,
        output_dir=Path(output_dir),
        on_job_finished=build_job_finished_callback(metrics),
    )
