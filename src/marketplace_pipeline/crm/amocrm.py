from __future__ import annotations

from pathlib import Path

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome, CrmTaskRequest
from marketplace_pipeline.domain.services.crm_task_factory import CrmTaskFactory
from marketplace_pipeline.infrastructure.adapters.crm.amocrm_gateway import (
    AmoCrmGateway,
    build_idempotency_store,
)
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient


class AmoCRMClient(AmoCrmGateway):
    """Legacy alias for ``AmoCrmGateway``."""

    def __init__(
        self,
        settings: Settings,
        http_client: HttpClient | None = None,
        *,
        idempotency_store_path: Path | None = None,
    ) -> None:
        store = build_idempotency_store(
            settings,
            idempotency_store_path or Path(settings.crm_idempotency_store_path),
        )
        super().__init__(settings, store, http_client=http_client)

    def create_task(self, payload: CrmTaskRequest) -> CrmTaskOutcome:
        return super().create_task(payload)


def format_product_lines(products: list[EnrichedProduct]) -> str:
    return CrmTaskFactory._format_lines(products)


__all__ = ["AmoCRMClient", "format_product_lines"]
