from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from marketplace_pipeline.application.dto.pipeline_result import PipelineResultDTO
from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome
from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient


@dataclass
class PipelineResult:
    """Legacy DTO wrapper for tests and scripts."""

    parser_result: CollectionResult
    enriched_products: list[EnrichedProduct]
    crm_tasks: list[CrmTaskOutcome]
    output_path: Path | None = None

    @classmethod
    def from_dto(cls, dto: PipelineResultDTO) -> PipelineResult:
        return cls(
            parser_result=dto.collection_result,
            enriched_products=dto.enriched_products,
            crm_tasks=dto.crm_tasks,
            output_path=dto.output_path,
        )


class Pipeline:
    """Legacy facade delegating to ``RunPipelineUseCase``."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: HttpClient | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._container = Container(
            settings,
            http_client=http_client,
            output_dir=output_dir,
        )

    def run(self) -> PipelineResult:
        return PipelineResult.from_dto(self._container.run_pipeline_use_case().execute())
