from __future__ import annotations

from typing import Protocol

from marketplace_pipeline.domain.models.pipeline_job import PipelineJob


class JobRunnerPort(Protocol):
    def submit(self, job: PipelineJob) -> None: ...

    def shutdown(self, wait: bool = True) -> None: ...
