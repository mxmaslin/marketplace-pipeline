from __future__ import annotations

from typing import Protocol

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob


class JobRepositoryPort(Protocol):
    def create(self, job: PipelineJob) -> PipelineJob: ...

    def get(self, job_id: str) -> PipelineJob | None: ...

    def update(self, job: PipelineJob) -> PipelineJob: ...

    def list_recent(self, limit: int = 20) -> list[PipelineJob]: ...

    def ping(self) -> bool: ...
