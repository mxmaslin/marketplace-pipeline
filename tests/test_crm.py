from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.crm.amocrm import AmoCRMClient
from marketplace_pipeline.llm.classifier import SegmentClassifier
from marketplace_pipeline.models import CRMTaskPayload, PriceSegment
from marketplace_pipeline.parser.mock import MockParser
from marketplace_pipeline.selectors import (
    build_crm_tasks,
    select_economy_top_cheap,
    select_premium_top_expensive,
)


@pytest.fixture
def enriched_products():
    settings = Settings(MOCK_LLM=True)
    products = MockParser(settings).collect(30).products
    return SegmentClassifier(settings).classify(products)


def test_selectors(enriched_products) -> None:
    premium = select_premium_top_expensive(enriched_products, limit=5)
    economy = select_economy_top_cheap(enriched_products, limit=5)

    assert len(premium) <= 5
    assert len(economy) <= 5
    if premium:
        assert all(p.segment == PriceSegment.PREMIUM for p in premium)
        prices = [p.price for p in premium]
        assert prices == sorted(prices, reverse=True)
    if economy:
        assert all(p.segment == PriceSegment.ECONOMY for p in economy)
        prices = [p.price for p in economy]
        assert prices == sorted(prices)


def test_build_crm_tasks(enriched_products) -> None:
    tasks = build_crm_tasks(enriched_products)
    assert 1 <= len(tasks) <= 2
    assert "URL" not in tasks[0].description  # URLs are in description as links
    assert "http" in tasks[0].description


def test_mock_crm(tmp_path: Path) -> None:
    client = AmoCRMClient(
        Settings(MOCK_CRM=True),
        idempotency_store_path=tmp_path / "crm_idempotency.json",
    )
    result = client.create_task(
        CRMTaskPayload(title="Test", description="- item: 100 RUB — https://example.com")
    )
    assert result.mocked is True
    assert result.task_id.startswith("mock-task-")
    assert result.reused is False


def test_amocrm_http(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="example",
        AMOCRM_ACCESS_TOKEN="token",
    )
    httpx_mock.add_response(
        json={"_embedded": {"tasks": []}},
        status_code=200,
    )
    httpx_mock.add_response(
        json={"_embedded": {"tasks": [{"id": 42}]}},
        status_code=200,
    )
    client = AmoCRMClient(
        settings,
        idempotency_store_path=tmp_path / "crm_idempotency.json",
    )
    result = client.create_task(CRMTaskPayload(title="T", description="D"))
    assert result.task_id == "42"
    assert result.mocked is False

    request = httpx_mock.get_requests()[0]
    assert "example.amocrm.ru/api/v4/tasks" in str(request.url)
    assert request.headers["Authorization"] == "Bearer token"
