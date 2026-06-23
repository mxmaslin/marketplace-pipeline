"""Tests for PipelineJobRunner background execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from marketplace_pipeline.config import Settings
from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob
from marketplace_pipeline.infrastructure.adapters.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from marketplace_pipeline.infrastructure.services.pipeline_job_runner import PipelineJobRunner


@pytest.fixture
def runner(tmp_path: Path) -> PipelineJobRunner:
    settings = Settings(
        MOCK_PARSER=True,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
    )
    repo = SqliteJobRepository(tmp_path / "jobs.sqlite")
    return PipelineJobRunner(settings, repo, output_dir=tmp_path, max_workers=1)


def test_job_runner_completes_successfully(runner: PipelineJobRunner) -> None:
    job = PipelineJob(collection_target=5)
    future = runner.submit(job)
    future.result(timeout=10)

    loaded = runner._job_repository.get(job.id)
    assert loaded is not None
    assert loaded.status == JobStatus.COMPLETED
    assert loaded.collected_count == 5
    assert loaded.finished_at is not None


def test_job_runner_marks_failed_on_pipeline_error(
    runner: PipelineJobRunner,
) -> None:
    job = PipelineJob(collection_target=5)
    runner._job_repository.create(job)

    mock_use_case = MagicMock()
    mock_use_case.execute.side_effect = RuntimeError("pipeline boom")

    with patch.object(runner, "_job_repository") as repo_mock:
        repo_mock.get.return_value = job
        with patch(
            "marketplace_pipeline.infrastructure.services.pipeline_job_runner.Container"
        ) as container_cls:
            container_cls.return_value.run_pipeline_use_case.return_value = mock_use_case
            container_cls.return_value.http_client.close = MagicMock()
            runner._execute(job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == "pipeline boom"
    repo_mock.update.assert_called()


def test_job_runner_missing_job_is_noop(runner: PipelineJobRunner) -> None:
    with patch.object(runner._job_repository, "get", return_value=None):
        runner._execute("missing-id")  # should not raise
