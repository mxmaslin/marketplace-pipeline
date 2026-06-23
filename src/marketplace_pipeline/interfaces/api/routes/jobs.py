from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketplace_pipeline.application.use_cases.pipeline_jobs import (
    GetPipelineJobUseCase,
    ListPipelineJobsUseCase,
    SubmitPipelineJobUseCase,
)
from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.interfaces.api.schemas.jobs import (
    JobCreateRequest,
    JobListResponse,
    JobResponse,
)

router = APIRouter(prefix="/pipeline/jobs", tags=["Pipeline Jobs"])


def _to_response(job: PipelineJob) -> JobResponse:
    return JobResponse.model_validate(job.model_dump())


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit pipeline job",
    description="Accepts pipeline run asynchronously. Poll GET /{job_id} for status.",
)
async def create_job(body: JobCreateRequest, request: Request) -> JobResponse:
    request.app.state.metrics.inc_http()
    settings = request.app.state.settings
    target = body.collection_target or settings.collection_target
    correlation_id = getattr(request.state, "request_id", None)

    job = PipelineJob(collection_target=target, correlation_id=correlation_id)
    SubmitPipelineJobUseCase(
        request.app.state.job_repository,
        request.app.state.job_runner,
    ).execute(job)
    request.app.state.metrics.inc_submitted()
    return _to_response(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
)
async def get_job(job_id: str, request: Request) -> JobResponse:
    request.app.state.metrics.inc_http()
    job = GetPipelineJobUseCase(request.app.state.job_repository).execute(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _to_response(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List recent jobs",
)
async def list_jobs(request: Request, limit: int = 20) -> JobListResponse:
    request.app.state.metrics.inc_http()
    jobs = ListPipelineJobsUseCase(request.app.state.job_repository).execute(limit=limit)
    items = [_to_response(job) for job in jobs]
    return JobListResponse(items=items, count=len(items))
