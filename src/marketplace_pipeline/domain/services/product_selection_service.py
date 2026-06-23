from __future__ import annotations

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.value_objects.price_segment import PriceSegment


class ProductSelectionService:
    """Domain service: select top-N products within a price segment."""

    @staticmethod
    def top_premium_by_price(
        products: list[EnrichedProduct], limit: int = 5
    ) -> list[EnrichedProduct]:
        premium = [p for p in products if p.segment == PriceSegment.PREMIUM]
        return sorted(premium, key=lambda p: p.price, reverse=True)[:limit]

    @staticmethod
    def top_economy_by_price(
        products: list[EnrichedProduct], limit: int = 5
    ) -> list[EnrichedProduct]:
        economy = [p for p in products if p.segment == PriceSegment.ECONOMY]
        return sorted(economy, key=lambda p: p.price)[:limit]
