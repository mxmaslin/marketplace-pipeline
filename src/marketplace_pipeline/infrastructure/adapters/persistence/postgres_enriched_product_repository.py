from __future__ import annotations

import logging
from pathlib import Path

from psycopg.types.json import Json

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.collection_result import CollectionResult

logger = logging.getLogger(__name__)


class PostgresEnrichedProductRepository:
    """Infrastructure adapter: persist enriched catalog snapshots to PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        import psycopg

        self._database_url = database_url
        self._psycopg = psycopg

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    def save(
        self,
        products: list[EnrichedProduct],
        collection_result: CollectionResult,
    ) -> Path:
        meta = collection_result.model_dump(mode="json")
        payload = [product.model_dump(mode="json") for product in products]
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO enriched_product_snapshots (meta, products)
                VALUES (%s, %s)
                RETURNING id
                """,
                (Json(meta), Json(payload)),
            ).fetchone()
            conn.commit()
        snapshot_id = row[0]
        output_path = Path(f"postgres://enriched_product_snapshots/{snapshot_id}")
        logger.info("Saved enriched dataset to %s", output_path)
        return output_path
