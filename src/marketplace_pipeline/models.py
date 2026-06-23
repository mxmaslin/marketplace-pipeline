"""
Backward-compatible model re-exports.

Prefer explicit imports from ``marketplace_pipeline.domain.*``.
"""

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome, CrmTaskRequest
from marketplace_pipeline.domain.value_objects.price_segment import PriceSegment

# Legacy aliases used in tests and docs
ParserResult = CollectionResult
CRMTaskPayload = CrmTaskRequest
CRMTaskResult = CrmTaskOutcome

__all__ = [
    "CRMTaskPayload",
    "CRMTaskResult",
    "EnrichedProduct",
    "ParserResult",
    "PriceSegment",
    "Product",
    "CollectionResult",
    "CrmTaskRequest",
    "CrmTaskOutcome",
]
