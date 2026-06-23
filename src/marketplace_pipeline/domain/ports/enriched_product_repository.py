from __future__ import annotations

from pathlib import Path
from typing import Protocol

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.collection_result import CollectionResult


class EnrichedProductRepositoryPort(Protocol):
    def save(
        self,
        products: list[EnrichedProduct],
        collection_result: CollectionResult,
    ) -> Path: ...
