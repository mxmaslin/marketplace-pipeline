from __future__ import annotations

import json
import logging
from pathlib import Path

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.infrastructure.io.atomic import atomic_write_text

logger = logging.getLogger(__name__)


class JsonEnrichedProductRepository:
    """Infrastructure adapter: persist enriched catalog to JSON file."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def save(
        self,
        products: list[EnrichedProduct],
        collection_result: CollectionResult,
    ) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "enriched_products.json"
        payload = {
            "meta": collection_result.model_dump(mode="json"),
            "products": [p.model_dump(mode="json") for p in products],
        }
        atomic_write_text(
            output_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        logger.info("Saved enriched dataset to %s", output_path)
        return output_path
