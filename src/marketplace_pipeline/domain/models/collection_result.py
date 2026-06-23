from __future__ import annotations

from pydantic import BaseModel

from marketplace_pipeline.domain.entities.product import Product


class CollectionResult(BaseModel):
    """Outcome of catalog collection (success, partial, or degraded)."""

    products: list[Product]
    target_count: int
    collected_count: int
    exhausted: bool
    degraded: bool = False
    error_message: str | None = None
