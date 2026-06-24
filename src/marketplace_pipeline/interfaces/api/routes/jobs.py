from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from marketplace_pipeline.application.use_cases.pipeline_jobs import (
    GetPipelineJobUseCase,
    ListPipelineJobsUseCase,
    SubmitPipelineJobUseCase,
)
from marketplace_pipeline.domain.exceptions import (
    PipelineConfigurationError,
    ProxyQuotaExhaustedError,
)
from marketplace_pipeline.domain.models.pipeline_job import PipelineJob
from marketplace_pipeline.domain.services.pipeline_prerequisites import (
    PipelinePrerequisites,
    validate_pipeline_prerequisites,
)
from marketplace_pipeline.domain.services.proxy_prerequisites import (
    ProxyPrerequisites,
    validate_proxy_prerequisites,
)
from marketplace_pipeline.infrastructure.composition.factories import build_proxy_quota_checker
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
async def create_job(
    body: JobCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    settings = request.app.state.settings
    target = body.collection_target or settings.collection_target
    correlation_id = getattr(request.state, "request_id", None)

    try:
        validate_pipeline_prerequisites(
            PipelinePrerequisites(
                mock_llm=settings.mock_llm,
                mock_crm=settings.mock_crm,
                openai_api_key=settings.openai_api_key,
                amocrm_subdomain=settings.amocrm_subdomain,
                amocrm_access_token=settings.amocrm_access_token,
            )
        )
    except PipelineConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    checker = build_proxy_quota_checker(settings)
    try:
        validate_proxy_prerequisites(
            ProxyPrerequisites(
                mock_parser=settings.mock_parser,
                ozon_proxy_list=settings.ozon_proxy_list,
                proxy_market_api_key=settings.proxy_market_api_key,
            ),
            quota_checker=checker,
        )
    except ProxyQuotaExhaustedError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    finally:
        if checker is not None and hasattr(checker, "close"):
            checker.close()

    job = PipelineJob(collection_target=target, correlation_id=correlation_id)
    job, is_replay = SubmitPipelineJobUseCase(
        request.app.state.job_repository,
        request.app.state.job_runner,
        request.app.state.job_idempotency_store,
    ).execute(job, idempotency_key=idempotency_key)
    if not is_replay:
        request.app.state.metrics.inc_submitted()
    return _to_response(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
)
async def get_job(job_id: str, request: Request) -> JobResponse:
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
    jobs = ListPipelineJobsUseCase(request.app.state.job_repository).execute(limit=limit)
    items = [_to_response(job) for job in jobs]
    return JobListResponse(items=items, count=len(items))
