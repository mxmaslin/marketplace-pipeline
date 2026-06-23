"""API integration tests."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from marketplace_pipeline.interfaces.api.app import create_app


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_PRODUCT_COUNT", "20")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.delenv("API_KEY", raising=False)
    with TestClient(create_app()) as client:
        yield client


def test_health(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "marketplace-pipeline"
    assert body["version"] == "0.5.0"


def test_ready(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["job_db_ok"] is True
    assert body["data_dir_writable"] is True


def test_metrics(api_client: TestClient) -> None:
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert "pipeline_jobs_submitted_total" in response.text
    assert "http_request_duration_ms_avg" in response.text


def test_submit_and_poll_job(api_client: TestClient) -> None:
    create = api_client.post("/api/v1/pipeline/jobs", json={"collection_target": 15})
    assert create.status_code == 202
    assert "X-Request-ID" in create.headers
    job_id = create.json()["id"]
    assert create.json()["status"] == "pending"

    poll = None
    for _ in range(50):
        poll = api_client.get(f"/api/v1/pipeline/jobs/{job_id}")
        assert poll.status_code == 200
        status = poll.json()["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(0.05)
    else:
        pytest.fail("job did not finish in time")

    assert poll is not None
    assert poll.json()["status"] == "completed"
    assert poll.json()["collected_count"] == 15
    assert poll.json()["classified_count"] == 15

    metrics = api_client.get("/metrics").text
    assert "pipeline_jobs_completed_total" in metrics
    assert "pipeline_jobs_submitted_total" in metrics


def test_list_jobs(api_client: TestClient) -> None:
    api_client.post("/api/v1/pipeline/jobs", json={})
    response = api_client.get("/api/v1/pipeline/jobs")
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_get_missing_job(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/pipeline/jobs/does-not-exist")
    assert response.status_code == 404


def test_api_key_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("API_KEY", "secret-key")

    with TestClient(create_app()) as client:
        denied = client.post("/api/v1/pipeline/jobs", json={"collection_target": 5})
        assert denied.status_code == 401

        allowed = client.post(
            "/api/v1/pipeline/jobs",
            json={"collection_target": 5},
            headers={"X-API-Key": "secret-key"},
        )
        assert allowed.status_code == 202


def test_rate_limit_returns_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "1")

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        blocked = client.get("/health")
        assert blocked.status_code == 429


def test_ready_checks_redis_when_celery_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("JOB_RUNNER_BACKEND", "celery")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    with patch(
        "marketplace_pipeline.interfaces.api.routes.health.ping_redis",
        return_value=True,
    ):
        with TestClient(create_app()) as client:
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json()["redis_ok"] is True


def test_pre_flight_validation_missing_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/pipeline/jobs", json={"collection_target": 5})
        assert response.status_code == 422
        assert "OPENAI_API_KEY" in response.json()["detail"]
