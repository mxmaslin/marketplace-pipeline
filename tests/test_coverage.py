"""Edge-case tests targeting uncovered branches."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings, get_settings
from marketplace_pipeline.crm.amocrm import AmoCRMClient, format_product_lines
from marketplace_pipeline.crm.idempotency import (
    IdempotencyStore,
    append_idempotency_marker,
    extract_idempotency_marker,
)
from marketplace_pipeline.domain.exceptions import CrmConfigurationError
from marketplace_pipeline.http_client import HttpClient
from marketplace_pipeline.llm.classifier import SegmentClassifier, _chunk
from marketplace_pipeline.models import CRMTaskPayload, PriceSegment, Product
from marketplace_pipeline.parser.mock import MockParser
from marketplace_pipeline.parser.ozon import OzonParser
from marketplace_pipeline.pipeline import Pipeline


def test_get_settings() -> None:
    assert get_settings().target_product_count == 10_000


def test_collection_target_full_mode() -> None:
    settings = Settings(DEMO_MODE=False, TARGET_PRODUCT_COUNT=5000)
    assert settings.collection_target == 5000


def test_idempotency_store_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    store = IdempotencyStore.load(path)
    assert store.get("any") is None


def test_append_idempotency_marker_idempotent() -> None:
    text = append_idempotency_marker("Hello", "key1")
    again = append_idempotency_marker(text, "key1")
    assert text == again


def test_extract_idempotency_marker_missing() -> None:
    assert extract_idempotency_marker("no marker here") is None
    assert extract_idempotency_marker("[pipeline:idempotency:abc") is None


def test_crm_idempotency_disabled_creates_duplicate(tmp_path: Path) -> None:
    settings = Settings(MOCK_CRM=True, CRM_IDEMPOTENCY_ENABLED=False)
    client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "s.json")
    payload = CRMTaskPayload(title="X", description="Y")
    first = client.create_task(payload)
    second = client.create_task(payload)
    assert first.reused is False
    assert second.reused is False


def test_amocrm_missing_credentials() -> None:
    client = AmoCRMClient(
        Settings(MOCK_CRM=False, CRM_IDEMPOTENCY_ENABLED=False),
    )
    with pytest.raises(CrmConfigurationError, match="AMOCRM_SUBDOMAIN"):
        client.create_task(CRMTaskPayload(title="T", description="D"))


def test_amocrm_unexpected_response(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="ex",
        AMOCRM_ACCESS_TOKEN="tok",
    )
    httpx_mock.add_response(json={"_embedded": {"tasks": []}})
    httpx_mock.add_response(json={"error": "bad"})
    client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "s.json")
    with pytest.raises(ValueError, match="Unexpected AmoCRM"):
        client.create_task(CRMTaskPayload(title="T", description="D"))


def test_amocrm_with_responsible_user(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="ex",
        AMOCRM_ACCESS_TOKEN="tok",
        AMOCRM_RESPONSIBLE_USER_ID=999,
    )
    httpx_mock.add_response(json={"_embedded": {"tasks": []}})
    httpx_mock.add_response(json={"_embedded": {"tasks": [{"id": 1}]}})
    client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "s.json")
    client.create_task(CRMTaskPayload(title="T", description="D"))
    create_req = httpx_mock.get_requests()[-1]
    body = json.loads(create_req.content)
    assert body[0]["responsible_user_id"] == 999


def test_amocrm_remote_pagination_finds_task(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="ex",
        AMOCRM_ACCESS_TOKEN="tok",
    )
    payload = CRMTaskPayload(title="Find", description="Me")
    from marketplace_pipeline.crm.idempotency import compute_idempotency_key

    key = compute_idempotency_key(payload)
    marked = append_idempotency_marker("body", key)

    full_page = [{"id": i, "text": "other"} for i in range(250)]
    httpx_mock.add_response(json={"_embedded": {"tasks": full_page}})
    httpx_mock.add_response(json={"_embedded": {"tasks": [{"id": 555, "text": marked}]}})

    client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "s.json")
    result = client.create_task(payload)
    assert result.reused is True
    assert result.task_id == "555"


def test_format_product_lines() -> None:
    from marketplace_pipeline.llm.classifier import SegmentClassifier
    from marketplace_pipeline.parser.mock import MockParser

    products = SegmentClassifier(Settings(MOCK_LLM=True)).classify(
        MockParser(Settings()).collect(1).products
    )
    text = format_product_lines(products)
    assert "RUB" in text
    assert "http" in text


def test_classifier_empty_products() -> None:
    assert SegmentClassifier(Settings()).classify([]) == []


def test_classifier_invalid_llm_response() -> None:
    classifier = SegmentClassifier(Settings(MOCK_LLM=True))
    with pytest.raises(ValueError, match="items list"):
        classifier._parse_segments('{"wrong": true}', expected_ids={"a"})


def test_classifier_invalid_segment_fallback() -> None:
    classifier = SegmentClassifier(Settings(MOCK_LLM=True))
    parsed = classifier._parse_segments(
        '{"items":[{"id":"x","segment":"Luxury"}]}',
        expected_ids={"x"},
    )
    assert parsed["x"] == PriceSegment.STANDARD


def test_classifier_mock_price_economy() -> None:
    classifier = SegmentClassifier(Settings(MOCK_LLM=True))
    product = Product(
        id="1",
        name="Generic",
        price=5_000,
        url="https://www.ozon.ru/product/1/",
        category="C",
        collected_at=datetime.now(tz=UTC),
    )
    assert classifier._mock_classify(product).segment == PriceSegment.ECONOMY


def test_classifier_mock_price_premium() -> None:
    classifier = SegmentClassifier(Settings(MOCK_LLM=True))
    product = Product(
        id="2",
        name="Generic",
        price=90_000,
        url="https://www.ozon.ru/product/2/",
        category="C",
        collected_at=datetime.now(tz=UTC),
    )
    assert classifier._mock_classify(product).segment == PriceSegment.PREMIUM


def test_chunk_helper() -> None:
    products = MockParser(Settings()).collect(5).products
    batches = list(_chunk(products, 2))
    assert len(batches) == 3


def test_http_client_post_retries_429(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200, json={"ok": True})
    client = HttpClient(max_retries=3, base_delay=0.01)
    response = client.post("https://example.com/post", json={"a": 1})
    assert response.status_code == 200


def test_ozon_collect_degraded(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=503)
    parser = OzonParser(Settings(MOCK_PARSER=False, HTTP_MAX_RETRIES=1))
    result = parser.collect(10)
    assert result.degraded is True
    assert result.collected_count == 0


def test_ozon_collect_exhausted_category(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"widgetStates": {}})
    parser = OzonParser(Settings(MOCK_PARSER=False))
    result = parser.collect(10)
    assert result.exhausted is True
    assert result.collected_count == 0


def test_ozon_skips_duplicate_and_invalid_price(httpx_mock: HTTPXMock) -> None:
    raw = (
        '{"sku":1,"title":"A","price":"100 ₽"}'
        '{"sku":1,"title":"A dup","price":"200 ₽"}'
        '{"sku":2,"title":"B","price":"free"}'
    )
    httpx_mock.add_response(json={"widgetStates": {"tileGridDesktop": raw}})
    parser = OzonParser(Settings(MOCK_PARSER=False))
    result = parser.collect(1)
    assert result.collected_count == 1


def test_pipeline_logs_exhausted(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    settings = Settings(
        MOCK_PARSER=False,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
        DEMO_PRODUCT_COUNT=5,
    )
    httpx_mock.add_response(json={"widgetStates": {}})
    result = Pipeline(settings, output_dir=tmp_path).run()
    assert result.parser_result.exhausted is True


def test_amocrm_remote_search_short_page_no_match(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="ex",
        AMOCRM_ACCESS_TOKEN="tok",
    )
    httpx_mock.add_response(json={"_embedded": {"tasks": [{"id": 1, "text": "other"}]}})
    httpx_mock.add_response(json={"_embedded": {"tasks": [{"id": 99}]}})
    client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "s.json")
    result = client.create_task(CRMTaskPayload(title="New", description="Task"))
    assert result.task_id == "99"
    assert result.reused is False


def test_main_module_entrypoint() -> None:
    import runpy

    with patch("marketplace_pipeline.interfaces.cli.main.main", return_value=0):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("marketplace_pipeline.interfaces.cli.main", run_name="__main__")
        assert exc.value.code == 0
