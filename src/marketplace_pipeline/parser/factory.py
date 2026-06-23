from __future__ import annotations

from marketplace_pipeline.infrastructure.adapters.parsers.mock_collector import MockCatalogCollector
from marketplace_pipeline.infrastructure.adapters.parsers.ozon_collector import OzonCatalogCollector
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient


def build_parser(
    settings: Settings,
    http_client: HttpClient | None = None,
) -> MockCatalogCollector | OzonCatalogCollector:
    if settings.mock_parser:
        return MockCatalogCollector(settings)
    return OzonCatalogCollector(settings, http_client=http_client)
