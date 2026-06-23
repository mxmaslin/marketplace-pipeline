from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class PipelineJobRunner:
    """Runs pipeline use cases in a background thread pool."""

    def __init__(
        self,
        settings: Settings,
        job_repository: JobRepositoryPort,
        *,
        output_dir: Path | None = None,
        max_workers: int = 2,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._output_dir = output_dir or Path("data")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pipeline")

    def submit(self, job: PipelineJob) -> Future[None]:
        self._job_repository.create(job)
        return self._executor.submit(self._execute, job.id)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _execute(self, job_id: str) -> None:
        job = self._job_repository.get(job_id)
        if job is None:
            logger.error("Job %s not found", job_id)
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(tz=UTC)
        self._job_repository.update(job)

        container = Container(self._settings, output_dir=self._output_dir)
        try:
            result = container.run_pipeline_use_case(job.collection_target).execute()
            job.status = JobStatus.COMPLETED
            job.collected_count = result.collection_result.collected_count
            job.classified_count = len(result.enriched_products)
            job.crm_tasks_count = len(result.crm_tasks)
            job.output_path = str(result.output_path) if result.output_path else None
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
        finally:
            job.finished_at = datetime.now(tz=UTC)
            self._job_repository.update(job)
            container.http_client.close()
