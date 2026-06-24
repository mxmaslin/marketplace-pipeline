"""Shared test helpers (not pytest fixtures)."""

from __future__ import annotations

from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient
from marketplace_pipeline.parser.ozon import OzonParser


def ozon_parser_for_httpx_mock(settings: Settings) -> OzonParser:
    """Ozon collector wired to shared HttpClient (pytest-httpx intercepts)."""
    return OzonParser(
        settings,
        http_client=HttpClient(
            max_retries=settings.http_max_retries,
            base_delay=settings.http_retry_base_delay,
            timeout=settings.ozon_request_timeout,
        ),
    )


def http_client_for_settings(settings: Settings) -> HttpClient:
    return HttpClient(
        max_retries=settings.http_max_retries,
        base_delay=settings.http_retry_base_delay,
        timeout=settings.ozon_request_timeout,
    )
