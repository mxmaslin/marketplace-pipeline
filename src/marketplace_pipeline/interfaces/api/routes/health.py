from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    ready: bool
    job_db: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from marketplace_pipeline.interfaces.api.app import API_VERSION

    return HealthResponse(status="ok", service="marketplace-pipeline", version=API_VERSION)


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> ReadyResponse:
    settings = request.app.state.settings
    return ReadyResponse(ready=True, job_db=settings.job_db_path)
