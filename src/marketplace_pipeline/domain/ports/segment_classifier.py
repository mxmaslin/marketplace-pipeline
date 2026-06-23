from __future__ import annotations

from typing import Protocol

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.entities.product import Product


class SegmentClassifierPort(Protocol):
    def classify(self, products: list[Product]) -> list[EnrichedProduct]: ...
