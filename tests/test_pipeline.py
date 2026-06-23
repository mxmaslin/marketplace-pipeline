import json
from pathlib import Path

import httpx
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.http_client import HttpClient, RateLimitError
from marketplace_pipeline.pipeline import Pipeline


def test_http_client_retries_on_429(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200, json={"ok": True})

    client = HttpClient(max_retries=3, base_delay=0.01, timeout=5.0)
    response = client.get("https://example.com/api")
    assert response.status_code == 200
    assert len(httpx_mock.get_requests()) == 2


def test_rate_limit_error() -> None:
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
    err = RateLimitError(response)
    assert "429" in str(err)


def test_pipeline_end_to_end(tmp_path: Path) -> None:
    settings = Settings(
        MOCK_PARSER=True,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
        DEMO_PRODUCT_COUNT=30,
    )
    result = Pipeline(settings, output_dir=tmp_path).run()

    assert result.parser_result.collected_count == 30
    assert len(result.enriched_products) == 30
    assert len(result.crm_tasks) >= 1
    assert result.output_path is not None
    assert result.output_path.exists()

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["meta"]["collected_count"] == 30
    assert len(payload["products"]) == 30


def test_pipeline_graceful_degradation(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    settings = Settings(
        MOCK_PARSER=False,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
        DEMO_PRODUCT_COUNT=10,
        HTTP_MAX_RETRIES=1,
        HTTP_RETRY_BASE_DELAY=0.01,
    )
    httpx_mock.add_response(status_code=500)

    pipeline = Pipeline(settings, output_dir=tmp_path)
    result = pipeline.run()

    assert result.parser_result.degraded is True
    assert result.parser_result.collected_count == 0
    assert result.enriched_products == []
    assert result.crm_tasks == []
