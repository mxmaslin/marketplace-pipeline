from __future__ import annotations

from typing import Protocol

from marketplace_pipeline.domain.models.collection_result import CollectionResult


class CatalogCollectorPort(Protocol):
    def collect(self, target_count: int) -> CollectionResult: ...
