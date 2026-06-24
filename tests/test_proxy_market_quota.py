from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError
from marketplace_pipeline.domain.services.proxy_prerequisites import (
    ProxyPrerequisites,
    is_proxy_quota_transport_error,
    validate_proxy_prerequisites,
)
from marketplace_pipeline.infrastructure.adapters.proxy.proxy_market_quota_checker import (
    ProxyMarketQuotaChecker,
    ProxyPackageQuota,
    format_bytes,
)


def test_format_bytes() -> None:
    assert format_bytes(512) == "512 B"
    assert format_bytes(2048) == "2 KB"
    assert format_bytes(1_048_576) == "1.0 MB"
    assert format_bytes(2_147_483_648) == "2.00 GB"


def test_is_proxy_quota_transport_error() -> None:
    assert is_proxy_quota_transport_error("traffic limit exceeded")
    assert is_proxy_quota_transport_error("Недостаточно трафика")
    assert not is_proxy_quota_transport_error("connection reset")


def test_validate_proxy_prerequisites_skips_mock_parser() -> None:
    checker = MagicMock()
    validate_proxy_prerequisites(
        ProxyPrerequisites(mock_parser=True, ozon_proxy_list="http://x", proxy_market_api_key="k"),
        quota_checker=checker,
    )
    checker.check_quota_available.assert_not_called()


def test_validate_proxy_prerequisites_calls_checker() -> None:
    checker = MagicMock()
    validate_proxy_prerequisites(
        ProxyPrerequisites(
            mock_parser=False,
            ozon_proxy_list="http://user:pass@host:10000",
            proxy_market_api_key="api-key",
        ),
        quota_checker=checker,
    )
    checker.check_quota_available.assert_called_once()


def test_proxy_market_quota_checker_ok(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        json={
            "data": [
                {
                    "id": 1,
                    "name": "Test 2 GB",
                    "total": 2_147_483_648,
                    "used": 1_048_576,
                    "is_active": True,
                }
            ]
        },
    )
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/balance/test-key",
        json={"balance": 10.0},
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key", min_remaining_bytes=1_048_576)
    checker.check_quota_available()
    checker.close()


def test_proxy_market_quota_checker_exhausted(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        json={
            "data": [
                {
                    "id": 1,
                    "name": "Test 100 Mb",
                    "total": 104_857_600,
                    "used": 104_857_600,
                    "is_active": True,
                }
            ]
        },
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key")
    with pytest.raises(ProxyQuotaExhaustedError, match="traffic exhausted"):
        checker.check_quota_available()
    checker.close()


def test_proxy_market_quota_checker_api_error_skips(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        status_code=400,
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key")
    checker.check_quota_available()
    checker.close()


def test_proxy_market_quota_checker_no_active_packages(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        json={"data": [{"id": 1, "name": "old", "total": 1000, "used": 0, "is_active": False}]},
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key")
    with pytest.raises(ProxyQuotaExhaustedError, match="no active traffic packages"):
        checker.check_quota_available()
    checker.close()


def test_proxy_market_quota_checker_balance_payload_invalid(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        json={
            "data": [
                {
                    "id": 1,
                    "name": "pkg",
                    "total": 2_147_483_648,
                    "used": 1_048_576,
                    "is_active": True,
                }
            ]
        },
    )
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/balance/test-key",
        json={"balance": "not-a-number"},
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key")
    checker.check_quota_available()
    checker.close()


def test_proxy_market_quota_checker_balance_api_error(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/v2/packages/test-key?page=1&perPage=50",
        json={
            "data": [
                {
                    "id": 1,
                    "name": "pkg",
                    "total": 2_147_483_648,
                    "used": 1_048_576,
                    "is_active": True,
                }
            ]
        },
    )
    httpx_mock.add_response(
        url="https://api.dashboard.proxy.market/dev-api/balance/test-key",
        status_code=503,
    )
    checker = ProxyMarketQuotaChecker(api_key="test-key")
    checker.check_quota_available()
    checker.close()


def test_proxy_package_remaining_bytes() -> None:
    package = ProxyPackageQuota(
        package_id=1,
        name="pkg",
        total_bytes=100,
        used_bytes=40,
        is_active=True,
    )
    assert package.remaining_bytes == 60


def test_ozon_http_raises_proxy_quota_on_transport_keyword() -> None:
    from marketplace_pipeline.infrastructure.http.ozon_http import OzonHttpClient

    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/smartfony-15502/",
        max_retries=1,
        proxy_list="http://user:pass@pool.proxy.market:10000",
    )

    class BrokenTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ProxyError("traffic limit exceeded on upstream proxy")

    broken = httpx.Client(transport=BrokenTransport())
    client._clients["http://user:pass@pool.proxy.market:10000"] = broken

    with pytest.raises(ProxyQuotaExhaustedError, match="traffic or balance exhausted"):
        client.get_composer_json(page_path="/category/smartfony-15502/")
    client.close()
