from __future__ import annotations

from pathlib import Path

from marketplace_pipeline.application.use_cases.run_pipeline import RunPipelineUseCase
from marketplace_pipeline.domain.ports.enriched_product_repository import (
    EnrichedProductRepositoryPort,
)
from marketplace_pipeline.domain.services.proxy_prerequisites import (
    ProxyPrerequisites,
    validate_proxy_prerequisites,
)
from marketplace_pipeline.infrastructure.adapters.crm.amocrm_gateway import AmoCrmGateway
from marketplace_pipeline.infrastructure.adapters.llm.openai_classifier import (
    OpenAiSegmentClassifier,
)
from marketplace_pipeline.infrastructure.adapters.parsers.mock_collector import MockCatalogCollector
from marketplace_pipeline.infrastructure.adapters.parsers.ozon_collector import OzonCatalogCollector
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient


class Container:
    """Composition root: wires ports to adapters from settings."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: HttpClient | None = None,
        ozon_collector_http_client: HttpClient | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.output_dir = output_dir or Path("data")
        self.http_client = http_client or HttpClient(
            max_retries=settings.http_max_retries,
            base_delay=settings.http_retry_base_delay,
            timeout=settings.ozon_request_timeout,
        )
        self._ozon_collector_http_client = ozon_collector_http_client

    def catalog_collector(self) -> MockCatalogCollector | OzonCatalogCollector:
        if self.settings.mock_parser:
            return MockCatalogCollector(self.settings)
        if self._ozon_collector_http_client is not None:
            return OzonCatalogCollector(
                self.settings,
                http_client=self._ozon_collector_http_client,
            )
        return OzonCatalogCollector(self.settings)

    def segment_classifier(self) -> OpenAiSegmentClassifier:
        return OpenAiSegmentClassifier(self.settings, http_client=self.http_client)

    def crm_gateway(self) -> AmoCrmGateway:
        from marketplace_pipeline.infrastructure.composition.factories import (
            build_idempotency_store,
        )

        store = build_idempotency_store(
            self.settings,
            self.output_dir,
            store_path=self.output_dir / "crm_idempotency.json",
        )
        return AmoCrmGateway(self.settings, store, http_client=self.http_client)

    def product_repository(self) -> EnrichedProductRepositoryPort:
        from marketplace_pipeline.infrastructure.composition.factories import (
            build_enriched_product_repository,
        )

        return build_enriched_product_repository(self.settings, self.output_dir)

    def run_pipeline_use_case(self, collection_target: int | None = None) -> RunPipelineUseCase:
        return RunPipelineUseCase(
            catalog_collector=self.catalog_collector(),
            segment_classifier=self.segment_classifier(),
            crm_gateway=self.crm_gateway(),
            product_repository=self.product_repository(),
            collection_target=collection_target or self.settings.collection_target,
        )

    def validate_proxy_prerequisites(self) -> None:
        from marketplace_pipeline.infrastructure.composition.factories import (
            build_proxy_quota_checker,
        )

        checker = build_proxy_quota_checker(self.settings)
        try:
            validate_proxy_prerequisites(
                ProxyPrerequisites(
                    mock_parser=self.settings.mock_parser,
                    ozon_proxy_list=self.settings.ozon_proxy_list,
                    proxy_market_api_key=self.settings.proxy_market_api_key,
                ),
                quota_checker=checker,
            )
        finally:
            if checker is not None and hasattr(checker, "close"):
                checker.close()
