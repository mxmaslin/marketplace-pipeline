from __future__ import annotations

from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.value_objects.price_segment import PriceSegment


class EnrichedProduct(Product):
    """Product enriched with consumer price segment."""

    segment: PriceSegment
