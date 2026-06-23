from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from marketplace_pipeline.domain.models.pipeline_job import JobStatus
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.logging.context import (
    reset_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger(__name__)

JobFinishedCallback = Callable[..., None]


def execute_pipeline_job(
    *,
    settings: Settings,
    job_repository: JobRepositoryPort,
    job_id: str,
    output_dir: Path,
    on_job_finished: JobFinishedCallback | None = None,
) -> None:
    """Shared job execution logic for thread pool and Celery workers."""
    job = job_repository.get(job_id)
    if job is None:
        logger.error("Job %s not found", job_id)
        return

    token = set_correlation_id(job.correlation_id)
    started = time.perf_counter()
    success = False
    job.status = JobStatus.RUNNING
    job.started_at = _utc_now()
    job_repository.update(job)

    container = Container(settings, output_dir=output_dir)
    try:
        result = container.run_pipeline_use_case(job.collection_target).execute()
        job.status = JobStatus.COMPLETED
        job.collected_count = result.collection_result.collected_count
        job.classified_count = len(result.enriched_products)
        job.crm_tasks_count = len(result.crm_tasks)
        job.output_path = str(result.output_path) if result.output_path else None
        success = True
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
    finally:
        job.finished_at = _utc_now()
        job_repository.update(job)
        container.http_client.close()
        duration = time.perf_counter() - started
        if on_job_finished is not None:
            on_job_finished(success=success, duration_seconds=duration)
        reset_correlation_id(token)


def _utc_now():
    from datetime import UTC, datetime

    return datetime.now(tz=UTC)
