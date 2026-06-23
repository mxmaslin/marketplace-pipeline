from __future__ import annotations

from marketplace_pipeline.infrastructure.workers import tasks as _tasks  # noqa: F401
from marketplace_pipeline.infrastructure.workers.celery_app import celery_app


def run_worker() -> None:
    celery_app.worker_main(argv=["worker", "--loglevel=info", "-Q", "celery"])
