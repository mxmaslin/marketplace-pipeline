from typing import Protocol

from marketplace_pipeline.domain.models.collection_result import CollectionResult


class BaseParser(Protocol):
    def collect(self, target_count: int) -> CollectionResult: ...
