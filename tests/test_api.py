"""API integration tests."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/pipeline/jobs").status_code == 200
        blocked = client.get("/api/v1/pipeline/jobs")
        assert blocked.status_code == 429


def test_redis_rate_limit_returns_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "1")

    mock_limiter = MagicMock()
    mock_limiter.allow.side_effect = [True, False]
    with patch(
        "marketplace_pipeline.infrastructure.rate_limit.redis_sliding_window.RedisSlidingWindowRateLimiter",
        return_value=mock_limiter,
    ):
        with TestClient(create_app()) as client:
            assert client.get("/api/v1/pipeline/jobs").status_code == 200
            blocked = client.get("/api/v1/pipeline/jobs")
            assert blocked.status_code == 429


def test_openapi_includes_security_when_api_key_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("API_KEY", "secret-key")

    with TestClient(create_app()) as client:
        schema = client.get("/openapi.json").json()
        assert "ApiKeyAuth" in schema["components"]["securitySchemes"]
        jobs_get = schema["paths"]["/api/v1/pipeline/jobs"]["get"]
        assert {"ApiKeyAuth": []} in jobs_get["security"]


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


def test_job_submit_idempotency_returns_same_job(api_client: TestClient) -> None:
    headers = {"Idempotency-Key": "idem-test-key-1"}
    first = api_client.post(
        "/api/v1/pipeline/jobs",
        json={"collection_target": 5},
        headers=headers,
    )
    second = api_client.post(
        "/api/v1/pipeline/jobs",
        json={"collection_target": 99},
        headers=headers,
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["collection_target"] == 5


def test_job_submit_idempotency_redis_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    stored: dict[str, str] = {}

    def fake_set(key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in stored:
            return False
        stored[key] = value
        return True

    def fake_get(key: str) -> str | None:
        return stored.get(key)

    mock_limiter = MagicMock()
    mock_limiter.allow.return_value = True
    with patch(
        "marketplace_pipeline.infrastructure.rate_limit.redis_sliding_window.RedisSlidingWindowRateLimiter",
        return_value=mock_limiter,
    ), patch("redis.from_url") as from_url:
        client = MagicMock()
        client.set.side_effect = fake_set
        client.get.side_effect = fake_get
        from_url.return_value = client
        with TestClient(create_app()) as test_client:
            headers = {"Idempotency-Key": "redis-idem-key"}
            first = test_client.post(
                "/api/v1/pipeline/jobs",
                json={"collection_target": 7},
                headers=headers,
            )
            second = test_client.post(
                "/api/v1/pipeline/jobs",
                json={"collection_target": 7},
                headers=headers,
            )
            assert first.status_code == 202
            assert second.status_code == 202
            assert first.json()["id"] == second.json()["id"]


def test_submit_job_proxy_quota_exhausted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError

    monkeypatch.setenv("MOCK_PARSER", "false")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("OZON_PROXY_LIST", "http://user:pass@pool.proxy.market:10000")
    monkeypatch.setenv("PROXY_MARKET_API_KEY", "test-key")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))

    checker = MagicMock()
    checker.check_quota_available.side_effect = ProxyQuotaExhaustedError(
        "PROXY_MARKET traffic exhausted"
    )
    with patch(
        "marketplace_pipeline.interfaces.api.routes.jobs.build_proxy_quota_checker",
        return_value=checker,
    ):
        with TestClient(create_app()) as client:
            response = client.post("/api/v1/pipeline/jobs", json={"collection_target": 10})
    assert response.status_code == 402
    assert "traffic exhausted" in response.json()["detail"]
    checker.close.assert_called_once()
