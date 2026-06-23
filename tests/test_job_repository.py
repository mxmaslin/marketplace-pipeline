"""Tests for SQLite job repository."""

from pathlib import Path

from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob
from marketplace_pipeline.infrastructure.adapters.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)


def test_sqlite_job_repository_crud(tmp_path: Path) -> None:
    repo = SqliteJobRepository(tmp_path / "jobs.sqlite")
    job = PipelineJob(collection_target=10, status=JobStatus.PENDING)
    repo.create(job)

    loaded = repo.get(job.id)
    assert loaded is not None
    assert loaded.collection_target == 10

    job.status = JobStatus.COMPLETED
    job.collected_count = 10
    repo.update(job)

    updated = repo.get(job.id)
    assert updated is not None
    assert updated.status == JobStatus.COMPLETED

    jobs = repo.list_recent(limit=5)
    assert len(jobs) == 1
