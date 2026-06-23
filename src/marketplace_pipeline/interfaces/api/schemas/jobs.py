from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from marketplace_pipeline.domain.models.pipeline_job import JobStatus


class JobCreateRequest(BaseModel):
    collection_target: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Override target SKU count; defaults to DEMO/TARGET env settings",
    )


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    collection_target: int
    collected_count: int | None
    classified_count: int | None
    crm_tasks_count: int | None
    output_path: str | None
    error_message: str | None
    correlation_id: str | None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobResponse]
    count: int
