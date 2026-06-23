"""Tests for domain services (pure unit tests)."""

from datetime import UTC, datetime

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.models.crm_task import CrmTaskRequest
from marketplace_pipeline.domain.services.crm_task_factory import CrmTaskFactory
from marketplace_pipeline.domain.services.idempotency_policy import (
    append_idempotency_marker,
    compute_task_idempotency_key,
)
from marketplace_pipeline.domain.services.product_selection_service import ProductSelectionService
from marketplace_pipeline.domain.value_objects.price_segment import PriceSegment


def _enriched(segment: PriceSegment, price: float, idx: int = 1) -> EnrichedProduct:
    return EnrichedProduct(
        id=f"p-{idx}",
        name=f"Item {idx}",
        price=price,
        url=f"https://www.ozon.ru/product/p-{idx}/",
        category="Test",
        collected_at=datetime.now(tz=UTC),
        segment=segment,
    )


def test_product_selection_service() -> None:
    svc = ProductSelectionService()
    products = [
        _enriched(PriceSegment.PREMIUM, 100_000, 1),
        _enriched(PriceSegment.PREMIUM, 50_000, 2),
        _enriched(PriceSegment.ECONOMY, 5_000, 3),
        _enriched(PriceSegment.ECONOMY, 3_000, 4),
    ]
    premium = svc.top_premium_by_price(products)
    economy = svc.top_economy_by_price(products)
    assert premium[0].price == 100_000
    assert economy[0].price == 3_000


def test_crm_task_factory() -> None:
    factory = CrmTaskFactory()
    tasks = factory.build_tasks(
        [
            _enriched(PriceSegment.PREMIUM, 90_000, 1),
            _enriched(PriceSegment.ECONOMY, 4_000, 2),
        ]
    )
    assert len(tasks) == 2
    assert "Премиум" in tasks[0].title


def test_idempotency_key_stable() -> None:
    task = CrmTaskRequest(title="T", description="body")
    assert compute_task_idempotency_key(task) == compute_task_idempotency_key(task)


def test_idempotency_marker() -> None:
    text = append_idempotency_marker("Hello", "abc")
    assert "[pipeline:idempotency:abc]" in text
