from __future__ import annotations

import logging
from datetime import UTC, datetime

from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

CATEGORY_NAME = "Смартфоны (mock)"


class MockCatalogCollector:
    """Infrastructure adapter: synthetic catalog for CI and local dev."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def collect(self, target_count: int) -> CollectionResult:
        products = [self._build_product(index) for index in range(1, target_count + 1)]
        logger.info("MOCK_PARSER generated %s products", len(products))
        return CollectionResult(
            products=products,
            target_count=target_count,
            collected_count=len(products),
            exhausted=len(products) < target_count,
            degraded=False,
        )

    def _build_product(self, index: int) -> Product:
        tier = index % 3
        if tier == 0:
            price = 5_000 + (index % 50) * 100
            name = f"BudgetPhone {index}"
        elif tier == 1:
            price = 25_000 + (index % 100) * 200
            name = f"MidRange {index}"
        else:
            price = 80_000 + (index % 30) * 1_000
            name = f"Flagship Pro {index}"

        return Product(
            id=f"mock-{index}",
            name=name,
            price=float(price),
            currency="RUB",
            url=f"https://www.ozon.ru/product/mock-{index}/",
            category=CATEGORY_NAME,
            collected_at=datetime.now(tz=UTC),
            description=f"{name}. Категория {CATEGORY_NAME}.",
        )
