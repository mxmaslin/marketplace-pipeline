from __future__ import annotations

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.domain.ports.job_runner import JobRunnerPort


class SubmitPipelineJobUseCase:
    """Enqueue a pipeline run and return job metadata immediately (202 pattern)."""

    def __init__(
        self,
        job_repository: JobRepositoryPort,
        job_runner: JobRunnerPort,
    ) -> None:
        self._job_repository = job_repository
        self._job_runner = job_runner

    def execute(self, job: PipelineJob) -> PipelineJob:
        self._job_runner.submit(job)
        return job


class GetPipelineJobUseCase:
    def __init__(self, job_repository: JobRepositoryPort) -> None:
        self._job_repository = job_repository

    def execute(self, job_id: str) -> PipelineJob | None:
        return self._job_repository.get(job_id)


class ListPipelineJobsUseCase:
    def __init__(self, job_repository: JobRepositoryPort) -> None:
        self._job_repository = job_repository

    def execute(self, limit: int = 20) -> list[PipelineJob]:
        return self._job_repository.list_recent(limit=limit)
