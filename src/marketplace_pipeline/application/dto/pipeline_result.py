from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome


@dataclass(frozen=True)
class PipelineResultDTO:
    collection_result: CollectionResult
    enriched_products: list[EnrichedProduct]
    crm_tasks: list[CrmTaskOutcome]
    output_path: Path | None = None
