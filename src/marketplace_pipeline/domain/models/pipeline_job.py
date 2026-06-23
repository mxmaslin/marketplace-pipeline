from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    collection_target: int
    collected_count: int | None = None
    classified_count: int | None = None
    crm_tasks_count: int | None = None
    output_path: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
