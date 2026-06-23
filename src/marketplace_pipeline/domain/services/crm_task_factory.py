from __future__ import annotations

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.crm_task import CrmTaskRequest
from marketplace_pipeline.domain.services.product_selection_service import ProductSelectionService


class CrmTaskFactory:
    """Builds CRM task requests from classified catalog."""

    def __init__(self, selection: ProductSelectionService | None = None) -> None:
        self._selection = selection or ProductSelectionService()

    def build_tasks(self, products: list[EnrichedProduct]) -> list[CrmTaskRequest]:
        tasks: list[CrmTaskRequest] = []
        premium = self._selection.top_premium_by_price(products)
        economy = self._selection.top_economy_by_price(products)

        if premium:
            tasks.append(
                CrmTaskRequest(
                    title="Топ-5 дорогих товаров сегмента Премиум",
                    description=self._format_lines(premium),
                )
            )
        if economy:
            tasks.append(
                CrmTaskRequest(
                    title="Топ-5 дешёвых товаров сегмента Эконом",
                    description=self._format_lines(economy),
                )
            )
        return tasks

    @staticmethod
    def _format_lines(products: list[EnrichedProduct]) -> str:
        return "\n".join(
            f"- {p.name}: {p.price:.0f} {p.currency} — {p.url}" for p in products
        )
