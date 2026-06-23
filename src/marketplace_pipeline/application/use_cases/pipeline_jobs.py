from __future__ import annotations

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.domain.ports.job_idempotency_store import JobIdempotencyStorePort
from marketplace_pipeline.domain.ports.job_repository import JobRepositoryPort
from marketplace_pipeline.domain.ports.job_runner import JobRunnerPort


class SubmitPipelineJobUseCase:
    """Enqueue a pipeline run and return job metadata immediately (202 pattern)."""

    def __init__(
        self,
        job_repository: JobRepositoryPort,
        job_runner: JobRunnerPort,
        job_idempotency_store: JobIdempotencyStorePort | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._job_runner = job_runner
        self._job_idempotency_store = job_idempotency_store

    def execute(
        self,
        job: PipelineJob,
        *,
        idempotency_key: str | None = None,
    ) -> tuple[PipelineJob, bool]:
        """Submit job. Returns (job, is_replay) where is_replay=True for idempotent hits."""
        if idempotency_key and self._job_idempotency_store is not None:
            replay = self._resolve_idempotent(idempotency_key)
            if replay is not None:
                return replay, True
            if not self._job_idempotency_store.reserve(idempotency_key, job.id):
                replay = self._resolve_idempotent(idempotency_key)
                if replay is not None:
                    return replay, True

        self._job_runner.submit(job)
        return job, False

    def _resolve_idempotent(self, idempotency_key: str) -> PipelineJob | None:
        assert self._job_idempotency_store is not None
        existing_id = self._job_idempotency_store.get(idempotency_key)
        if existing_id is None:
            return None
        return self._job_repository.get(existing_id)


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
