from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.services.pipeline_job_executor import (
    JobFinishedCallback,
    execute_pipeline_job,
)


class PipelineJobRunner:
    """Runs pipeline use cases in a background thread pool (single-node)."""

    def __init__(
        self,
        settings: Settings,
        job_repository: JobRepositoryPort,
        *,
        output_dir: Path | None = None,
        max_workers: int = 2,
        on_job_finished: JobFinishedCallback | None = None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._output_dir = output_dir or Path("data")
        self._on_job_finished = on_job_finished
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pipeline")

    def submit(self, job: PipelineJob) -> None:
        self._job_repository.create(job)
        self._executor.submit(self._execute, job.id)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _execute(self, job_id: str) -> None:
        execute_pipeline_job(
            settings=self._settings,
            job_repository=self._job_repository,
            job_id=job_id,
            output_dir=self._output_dir,
            on_job_finished=self._on_job_finished,
        )
