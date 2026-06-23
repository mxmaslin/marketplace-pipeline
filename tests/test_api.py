"""API integration tests."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

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
    with TestClient(create_app()) as client:
        yield client


def test_health(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "marketplace-pipeline"


def test_ready(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_metrics(api_client: TestClient) -> None:
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert "pipeline_jobs_submitted_total" in response.text


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


def test_list_jobs(api_client: TestClient) -> None:
    api_client.post("/api/v1/pipeline/jobs", json={})
    response = api_client.get("/api/v1/pipeline/jobs")
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_get_missing_job(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/pipeline/jobs/does-not-exist")
    assert response.status_code == 404
