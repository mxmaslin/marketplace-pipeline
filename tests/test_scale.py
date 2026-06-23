"""Multi-node scale stack tests (mocked backends)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from marketplace_pipeline.config import Settings
from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob
from marketplace_pipeline.domain.ports.idempotency_store import IdempotencyRecord
from marketplace_pipeline.domain.services.pipeline_prerequisites import (
    PipelinePrerequisites,
    validate_pipeline_prerequisites,
)
from marketplace_pipeline.infrastructure.composition.factories import (
    build_idempotency_store,
    build_job_repository,
    build_job_runner,
    ping_redis,
)
from marketplace_pipeline.infrastructure.config.settings import Settings as LayeredSettings
from marketplace_pipeline.infrastructure.logging.setup import configure_logging
from marketplace_pipeline.interfaces.api.metrics import MetricsRegistry


def test_settings_validate_postgres_requires_database_url() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        LayeredSettings(JOB_STORE_BACKEND="postgres", DATABASE_URL="")


def test_settings_validate_celery_requires_broker() -> None:
    with pytest.raises(ValueError, match="CELERY_BROKER_URL"):
        LayeredSettings(JOB_RUNNER_BACKEND="celery", REDIS_URL="", CELERY_BROKER_URL="")


def test_validate_pipeline_prerequisites_amocrm() -> None:
    from marketplace_pipeline.domain.exceptions import PipelineConfigurationError

    with pytest.raises(PipelineConfigurationError, match="AMOCRM"):
        validate_pipeline_prerequisites(
            PipelinePrerequisites(
                mock_llm=True,
                mock_crm=False,
                openai_api_key="",
                amocrm_subdomain="",
                amocrm_access_token="tok",
            )
        )


def test_build_job_repository_sqlite(tmp_path: Path) -> None:
    settings = Settings(JOB_DB_PATH=str(tmp_path / "jobs.sqlite"))
    repo = build_job_repository(settings)
    assert repo.ping() is True


def test_build_job_repository_postgres_mock() -> None:
    settings = Settings(
        JOB_STORE_BACKEND="postgres",
        DATABASE_URL="postgresql://user:pass@localhost/db",
    )
    with patch(
        "marketplace_pipeline.infrastructure.adapters.persistence.postgres_job_repository.PostgresJobRepository"
    ) as repo_cls:
        instance = MagicMock()
        instance.ping.return_value = True
        repo_cls.return_value = instance
        repo = build_job_repository(settings)
        assert repo.ping() is True


def test_build_idempotency_store_redis_mock() -> None:
    settings = Settings(
        CRM_IDEMPOTENCY_BACKEND="redis",
        REDIS_URL="redis://localhost:6379/0",
    )
    with patch("redis.from_url") as from_url:
        client = MagicMock()
        from_url.return_value = client
        store = build_idempotency_store(settings, Path("data"))
        record = IdempotencyRecord(task_id="1", title="t", idempotency_key="key")
        store.put("key", record)
        client.set.assert_called_once()
        client.get.return_value = record.model_dump_json()
        assert store.get("key") is not None
        assert store.ping() is True


def test_celery_job_runner_enqueues_task() -> None:
    settings = Settings(
        JOB_RUNNER_BACKEND="celery",
        REDIS_URL="redis://localhost:6379/0",
        JOB_DB_PATH="data/jobs.sqlite",
    )
    repo = MagicMock()
    job = PipelineJob(collection_target=3)

    with patch(
        "marketplace_pipeline.infrastructure.services.celery_job_runner.execute_pipeline_job_task"
    ) as task_mock:
        runner = build_job_runner(settings, repo, output_dir=Path("data"))
        runner.submit(job)
        runner.shutdown()

    repo.create.assert_called_once_with(job)
    task_mock.delay.assert_called_once_with(job.id)


def test_metrics_registry_uses_redis_counters() -> None:
    with patch("redis.from_url") as from_url:
        client = MagicMock()
        client.get.side_effect = lambda key: {
            "metrics:pipeline_jobs_submitted": "2",
            "metrics:pipeline_jobs_completed": "1",
            "metrics:pipeline_jobs_failed": "0",
        }.get(key)
        from_url.return_value = client
        metrics = MetricsRegistry(redis_url="redis://localhost:6379/0")
        metrics.inc_submitted()
        metrics.inc_completed()
        metrics.inc_failed()
        text = metrics.render_prometheus()
        assert "pipeline_jobs_submitted_total 2" in text
        assert "pipeline_jobs_completed_total 1" in text


def test_ping_redis_success() -> None:
    with patch("redis.from_url") as from_url:
        from_url.return_value.ping.return_value = True
        assert ping_redis("redis://localhost:6379/0") is True


def test_ping_redis_failure() -> None:
    with patch("redis.from_url", side_effect=OSError("down")):
        assert ping_redis("redis://localhost:6379/0") is False


def test_postgres_job_repository_operations() -> None:
    from marketplace_pipeline.infrastructure.adapters.persistence.postgres_job_repository import (
        PostgresJobRepository,
    )

    job = PipelineJob(collection_target=5, status=JobStatus.PENDING)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {
        "id": job.id,
        "status": job.status.value,
        "created_at": job.created_at,
        "started_at": None,
        "finished_at": None,
        "collection_target": job.collection_target,
        "collected_count": None,
        "classified_count": None,
        "crm_tasks_count": None,
        "output_path": None,
        "error_message": None,
        "correlation_id": None,
    }
    mock_conn.execute.return_value.fetchall.return_value = [
        mock_conn.execute.return_value.fetchone.return_value
    ]

    with patch.object(PostgresJobRepository, "_init_schema"):
        with patch.object(PostgresJobRepository, "_connect") as connect:
            connect.return_value.__enter__.return_value = mock_conn
            connect.return_value.__exit__.return_value = False
            repo = PostgresJobRepository("postgresql://localhost/test")
            assert repo.ping() is True
            repo.create(job)
            loaded = repo.get(job.id)
            assert loaded is not None
            job.status = JobStatus.COMPLETED
            repo.update(job)
            assert repo.list_recent(limit=1)


def test_celery_task_invokes_executor() -> None:
    with patch(
        "marketplace_pipeline.infrastructure.workers.tasks.execute_pipeline_job"
    ) as exec_mock, patch(
        "marketplace_pipeline.infrastructure.workers.tasks.build_job_repository"
    ), patch(
        "marketplace_pipeline.infrastructure.workers.tasks.get_settings"
    ), patch(
        "marketplace_pipeline.infrastructure.workers.tasks.configure_logging"
    ), patch(
        "marketplace_pipeline.infrastructure.workers.tasks.MetricsRegistry"
    ), patch(
        "marketplace_pipeline.infrastructure.workers.tasks.Container"
    ):
        from marketplace_pipeline.infrastructure.workers.tasks import execute_pipeline_job_task

        execute_pipeline_job_task("job-1")
        exec_mock.assert_called_once()
        assert exec_mock.call_args.kwargs["job_id"] == "job-1"


def test_setup_sentry_initializes_sdk() -> None:
    mock_sdk = MagicMock()
    fastapi_mod = MagicMock(FastApiIntegration=MagicMock())
    celery_mod = MagicMock(CeleryIntegration=MagicMock())
    with patch.dict(
        "sys.modules",
        {
            "sentry_sdk": mock_sdk,
            "sentry_sdk.integrations.fastapi": fastapi_mod,
            "sentry_sdk.integrations.celery": celery_mod,
        },
    ):
        from marketplace_pipeline.infrastructure.observability.tracing import setup_sentry

        setup_sentry(dsn="https://example.com/1", environment="test")
        mock_sdk.init.assert_called_once()


def test_setup_opentelemetry() -> None:
    mock_trace = MagicMock()
    mock_provider = MagicMock()
    mock_exporter = MagicMock()
    mock_processor = MagicMock()
    mock_resource = MagicMock()
    mock_instrumentor = MagicMock()
    mock_httpx = MagicMock()
    trace_mod = MagicMock(TracerProvider=MagicMock(return_value=mock_provider))
    with patch.dict(
        "sys.modules",
        {
            "opentelemetry": MagicMock(trace=mock_trace),
            "opentelemetry.exporter.otlp.proto.http.trace_exporter": MagicMock(
                OTLPSpanExporter=MagicMock(return_value=mock_exporter)
            ),
            "opentelemetry.instrumentation.fastapi": MagicMock(
                FastAPIInstrumentor=mock_instrumentor
            ),
            "opentelemetry.instrumentation.httpx": MagicMock(
                HTTPXClientInstrumentor=MagicMock(return_value=mock_httpx)
            ),
            "opentelemetry.sdk.resources": MagicMock(Resource=mock_resource),
            "opentelemetry.sdk.trace": trace_mod,
            "opentelemetry.sdk.trace.export": MagicMock(
                BatchSpanProcessor=MagicMock(return_value=mock_processor)
            ),
        },
    ):
        from marketplace_pipeline.infrastructure.observability.tracing import setup_opentelemetry

        setup_opentelemetry(MagicMock(), service_name="test", otlp_endpoint="http://localhost:4318/v1/traces")
        mock_trace.set_tracer_provider.assert_called_once()


def test_configure_logging_json() -> None:
    configure_logging("INFO", json_logs=True)
