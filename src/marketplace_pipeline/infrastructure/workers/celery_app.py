from __future__ import annotations

from celery import Celery

from marketplace_pipeline.infrastructure.config.settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    broker = settings.celery_broker_url or settings.redis_url
    app = Celery(
        "marketplace_pipeline",
        broker=broker,
        backend=broker,
        include=["marketplace_pipeline.infrastructure.workers.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = create_celery_app()
