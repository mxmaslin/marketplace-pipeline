"""Legacy selectors — domain logic lives in ``domain.services``."""

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.crm_task import CrmTaskRequest
from marketplace_pipeline.domain.services.crm_task_factory import CrmTaskFactory
from marketplace_pipeline.domain.services.product_selection_service import ProductSelectionService

_selection = ProductSelectionService()
_factory = CrmTaskFactory(_selection)

select_premium_top_expensive = _selection.top_premium_by_price
select_economy_top_cheap = _selection.top_economy_by_price


def build_crm_tasks(products: list[EnrichedProduct]) -> list[CrmTaskRequest]:
    return _factory.build_tasks(products)


# Legacy alias
CRMTaskPayload = CrmTaskRequest

__all__ = [
    "build_crm_tasks",
    "select_economy_top_cheap",
    "select_premium_top_expensive",
]
