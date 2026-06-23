from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.composition.factories import ping_redis

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    ready: bool
    job_store: str
    job_db_ok: bool
    data_dir_writable: bool
    redis_ok: bool | None
    checks: list[str]


def _check_data_dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ready_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError as exc:
        logger.warning("Data dir not writable %s: %s", path, exc)
        return False


def _needs_redis(settings: object) -> bool:
    from marketplace_pipeline.infrastructure.config.settings import Settings

    if not isinstance(settings, Settings):
        return False
    return (
        settings.job_runner_backend == "celery"
        or settings.crm_idempotency_backend == "redis"
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from marketplace_pipeline.interfaces.api.app import API_VERSION

    return HealthResponse(status="ok", service="marketplace-pipeline", version=API_VERSION)


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request, response: Response) -> ReadyResponse:
    settings = request.app.state.settings
    job_repo = request.app.state.job_repository
    output_dir = Container(settings).output_dir

    job_db_ok = job_repo.ping()
    data_dir_ok = _check_data_dir_writable(output_dir)
    redis_ok: bool | None = None
    checks: list[str] = []
    if not job_db_ok:
        checks.append("job_store_unreachable")
    if not data_dir_ok:
        checks.append("data_dir_not_writable")
    if _needs_redis(settings):
        redis_ok = ping_redis(settings.redis_url)
        if not redis_ok:
            checks.append("redis_unreachable")

    is_ready = job_db_ok and data_dir_ok and (redis_ok is not False)
    if not is_ready:
        response.status_code = 503

    return ReadyResponse(
        ready=is_ready,
        job_store=settings.job_store_label,
        job_db_ok=job_db_ok,
        data_dir_writable=data_dir_ok,
        redis_ok=redis_ok,
        checks=checks,
    )
