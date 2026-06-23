from __future__ import annotations

import logging

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.workers.tasks import execute_pipeline_job_task

logger = logging.getLogger(__name__)


class CeleryJobRunner:
    """Enqueues pipeline jobs to Celery workers (multi-node)."""

    def __init__(
        self,
        settings: Settings,
        job_repository: JobRepositoryPort,
        *,
        output_dir: object = None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        _ = output_dir

    def submit(self, job: PipelineJob) -> None:
        self._job_repository.create(job)
        execute_pipeline_job_task.delay(job.id)
        logger.info("Enqueued Celery job %s", job.id)

    def shutdown(self, wait: bool = True) -> None:
        _ = wait
