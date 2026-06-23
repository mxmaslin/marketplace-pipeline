from __future__ import annotations

import logging

from marketplace_pipeline.application.dto.pipeline_result import PipelineResultDTO
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.domain.ports.catalog_collector import CatalogCollectorPort
from marketplace_pipeline.domain.ports.crm_gateway import CrmGatewayPort
from marketplace_pipeline.domain.ports.enriched_product_repository import (
    EnrichedProductRepositoryPort,
)
from marketplace_pipeline.domain.ports.segment_classifier import SegmentClassifierPort
from marketplace_pipeline.domain.services.crm_task_factory import CrmTaskFactory

logger = logging.getLogger(__name__)


class RunPipelineUseCase:
    """Application use case: collect → classify → CRM → persist."""

    def __init__(
        self,
        catalog_collector: CatalogCollectorPort,
        segment_classifier: SegmentClassifierPort,
        crm_gateway: CrmGatewayPort,
        product_repository: EnrichedProductRepositoryPort,
        crm_task_factory: CrmTaskFactory | None = None,
        *,
        collection_target: int,
    ) -> None:
        self._catalog_collector = catalog_collector
        self._segment_classifier = segment_classifier
        self._crm_gateway = crm_gateway
        self._product_repository = product_repository
        self._crm_task_factory = crm_task_factory or CrmTaskFactory()
        self._collection_target = collection_target

    def execute(self) -> PipelineResultDTO:
        logger.info("Starting pipeline, target=%s products", self._collection_target)

        collection = self._catalog_collector.collect(self._collection_target)
        self._log_collection_status(collection)

        enriched = self._segment_classifier.classify(collection.products)
        logger.info("Classified %s products", len(enriched))

        task_requests = self._crm_task_factory.build_tasks(enriched)
        crm_outcomes = [self._crm_gateway.create_task(task) for task in task_requests]
        created = sum(1 for task in crm_outcomes if not task.reused)
        reused = sum(1 for task in crm_outcomes if task.reused)
        logger.info("CRM tasks: created=%s reused=%s total=%s", created, reused, len(crm_outcomes))

        output_path = self._product_repository.save(enriched, collection)
        return PipelineResultDTO(
            collection_result=collection,
            enriched_products=enriched,
            crm_tasks=crm_outcomes,
            output_path=output_path,
        )

    @staticmethod
    def _log_collection_status(result: CollectionResult) -> None:
        if result.degraded:
            logger.warning(
                "Parser degraded: collected %s/%s. Error: %s",
                result.collected_count,
                result.target_count,
                result.error_message,
            )
        elif result.exhausted and result.collected_count < result.target_count:
            logger.warning(
                "Category exhausted: collected %s/%s (acceptable when no more records)",
                result.collected_count,
                result.target_count,
            )
        else:
            logger.info("Collected %s/%s products", result.collected_count, result.target_count)
