from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from marketplace_pipeline.infrastructure.adapters.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.config.settings import get_settings
from marketplace_pipeline.infrastructure.services.pipeline_job_runner import PipelineJobRunner
from marketplace_pipeline.interfaces.api.metrics import MetricsRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    output_dir = Container(settings).output_dir
    job_repo = SqliteJobRepository(Path(settings.job_db_path))
    job_runner = PipelineJobRunner(
        settings,
        job_repo,
        output_dir=output_dir,
        max_workers=settings.api_job_workers,
    )
    app.state.settings = settings
    app.state.job_repository = job_repo
    app.state.job_runner = job_runner
    app.state.metrics = MetricsRegistry()
    logger.info("API started: job_db=%s workers=%s", settings.job_db_path, settings.api_job_workers)
    yield
    job_runner.shutdown(wait=True)
    logger.info("API shutdown complete")
