"""Tests for Ozon anti-bot HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.ozon_http import (
    BrowserProfile,
    OzonAntiBotError,
    OzonHttpClient,
    SessionFingerprint,
    browser_headers,
    build_ozon_http_client_from_settings,
    parse_cookie_header,
    parse_proxy_list,
)


def test_parse_proxy_list() -> None:
    assert parse_proxy_list("") == []
    assert parse_proxy_list("http://a:1, http://b:2") == ["http://a:1", "http://b:2"]


def test_parse_cookie_header() -> None:
    cookies = parse_cookie_header("foo=bar; baz=qux")
    assert cookies == {"foo": "bar", "baz": "qux"}


def _chrome_fingerprint() -> SessionFingerprint:
    profile = BrowserProfile(
        name="chrome",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"macOS"',
    )
    return SessionFingerprint(profile=profile, viewport_width=1920, viewport_height=1080)


def test_browser_headers_chrome_includes_sec_ch_ua() -> None:
    headers = browser_headers(fingerprint=_chrome_fingerprint(), referer="https://www.ozon.ru/")
    assert "sec-ch-ua" in headers
    assert headers["sec-ch-ua-mobile"] == "?0"
    assert headers["Viewport-Width"] == "1920"


def test_browser_headers_safari_omits_sec_ch_ua() -> None:
    profile = BrowserProfile(
        name="safari",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ),
    )
    fingerprint = SessionFingerprint(profile=profile, viewport_width=1440, viewport_height=900)
    headers = browser_headers(fingerprint=fingerprint, referer="https://www.ozon.ru/")
    assert "sec-ch-ua" not in headers
    assert headers["Viewport-Width"] == "1440"


def test_browser_headers_yandex() -> None:
    profile = BrowserProfile(
        name="yandex",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 YaBrowser/24.3.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="122", "YaBrowser";v="24", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
    )
    fingerprint = SessionFingerprint(profile=profile, viewport_width=1366, viewport_height=768)
    headers = browser_headers(fingerprint=fingerprint, referer="https://www.ozon.ru/")
    assert "YaBrowser" in headers["sec-ch-ua"]
    assert headers["Viewport-Width"] == "1366"


def test_browser_headers_mobile_viewport_sets_sec_ch_ua_mobile() -> None:
    profile = BrowserProfile(name="safari", user_agent="Mozilla/5.0 Safari/605.1.15")
    fingerprint = SessionFingerprint(profile=profile, viewport_width=390, viewport_height=844)
    headers = browser_headers(fingerprint=fingerprint, referer="https://www.ozon.ru/")
    assert headers["sec-ch-ua-mobile"] == "?1"


def test_get_composer_json_success() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        warmup_session=False,
        request_delay_seconds=0,
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"widgetStates": {"tileGridDesktop": "{}"}}
    mock_response.raise_for_status = MagicMock()
    mock_response.cookies = {}

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response
    mock_http.cookies = MagicMock()
    mock_http.cookies.set = MagicMock()

    with patch.object(client, "_client_for_proxy", return_value=mock_http):
        payload = client.get_composer_json(page_path="/category/test/")

    assert "widgetStates" in payload


def test_get_composer_json_raises_after_403_retries() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        warmup_session=False,
        request_delay_seconds=0,
        max_retries=1,
        proxy_list="http://proxy-a:8080",
    )
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = '{"incidentId":"fab_test"}'
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403",
        request=httpx.Request("GET", "https://www.ozon.ru"),
        response=mock_response,
    )
    mock_response.cookies = {}

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response
    mock_http.cookies = MagicMock()
    mock_http.cookies.set = MagicMock()
    mock_http.close = MagicMock()

    with patch.object(client, "_client_for_proxy", return_value=mock_http):
        with pytest.raises(OzonAntiBotError):
            client.get_composer_json(page_path="/category/test/")


def test_get_composer_json_raises_proxy_quota_on_http_402() -> None:
    from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError

    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        warmup_session=False,
        request_delay_seconds=0,
        max_retries=1,
    )
    mock_response = MagicMock()
    mock_response.status_code = 402
    mock_response.text = "payment required"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "402",
        request=httpx.Request("GET", "https://www.ozon.ru"),
        response=mock_response,
    )
    mock_response.cookies = {}
    mock_http = MagicMock()
    mock_http.get.return_value = mock_response
    mock_http.cookies = MagicMock()
    mock_http.cookies.set = MagicMock()

    with patch.object(client, "_client_for_proxy", return_value=mock_http):
        with pytest.raises(ProxyQuotaExhaustedError, match="HTTP 402"):
            client.get_composer_json(page_path="/category/test/")


def test_close_releases_clients() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        warmup_session=False,
    )
    mock_http = MagicMock()
    mock_http.cookies = MagicMock()
    mock_http.cookies.set = MagicMock()
    with patch(
        "marketplace_pipeline.infrastructure.http.ozon_http.httpx.Client",
        return_value=mock_http,
    ):
        client._client_for_proxy(None)
        client.close()
    mock_http.close.assert_called_once()


def test_fingerprint_sticky_per_proxy() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        rotate_user_agents=True,
    )
    first = client._fingerprint_for_proxy("http://proxy-a:8080")
    second = client._fingerprint_for_proxy("http://proxy-a:8080")
    other = client._fingerprint_for_proxy("http://proxy-b:8080")
    assert first is second
    assert first is not other


def test_fingerprint_fixed_when_rotation_disabled() -> None:
    profile = BrowserProfile(name="chrome", user_agent="Mozilla/5.0 Chrome/122.0.0.0")
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        rotate_user_agents=False,
        browser_profiles=(profile,),
    )
    fp = client._fingerprint_for_proxy(None)
    assert fp.profile.user_agent == "Mozilla/5.0 Chrome/122.0.0.0"
    assert fp.viewport_width == 1920


def test_throttle_uses_random_delay_range() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        request_delay_min_seconds=1.0,
        request_delay_max_seconds=2.0,
    )
    with patch(
        "marketplace_pipeline.infrastructure.http.ozon_http.random.uniform",
        return_value=1.5,
    ) as mock_uniform:
        assert client._next_request_delay() == 1.5
    mock_uniform.assert_called_once_with(1.0, 2.0)


def test_throttle_fixed_delay_backward_compat() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        request_delay_seconds=1.25,
    )
    assert client._next_request_delay() == 1.25


def test_merge_response_cookies_from_warmup() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        warmup_session=True,
        request_delay_seconds=0,
    )
    warm_response = MagicMock()
    warm_response.status_code = 200
    warm_response.cookies = httpx.Cookies()
    warm_response.cookies.set("server", "abc", domain=".ozon.ru")

    api_response = MagicMock()
    api_response.status_code = 200
    api_response.json.return_value = {"widgetStates": {"x": "{}"}}
    api_response.raise_for_status = MagicMock()
    api_response.cookies = httpx.Cookies()

    mock_http = MagicMock()
    mock_http.get.side_effect = [warm_response, api_response]
    jar = httpx.Cookies()
    mock_http.cookies = jar

    with patch.object(client, "_client_for_proxy", return_value=mock_http):
        client.get_composer_json(page_path="/category/test/")

    assert jar.get("server") == "abc"


def test_build_ozon_http_client_from_settings() -> None:
    settings = Settings(
        OZON_REQUEST_DELAY_MIN_SECONDS=0.5,
        OZON_REQUEST_DELAY_MAX_SECONDS=1.5,
        OZON_COOKIE="foo=bar",
    )
    client = build_ozon_http_client_from_settings(settings)
    assert client._request_delay_min_seconds == 0.5
    assert client._request_delay_max_seconds == 1.5
    assert client._static_cookies == {"foo": "bar"}


def test_build_ozon_http_client_from_settings_rejects_wrong_type() -> None:
    with pytest.raises(TypeError, match="settings must be Settings"):
        build_ozon_http_client_from_settings(object())


def test_static_cookies_applied_on_client_creation() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
        cookie_header="foo=bar",
    )
    mock_http = MagicMock()
    mock_http.cookies = MagicMock()
    with patch(
        "marketplace_pipeline.infrastructure.http.ozon_http.httpx.Client",
        return_value=mock_http,
    ):
        client._client_for_proxy("http://user:pass@proxy:8080")
    mock_http.cookies.set.assert_called_once_with("foo", "bar", domain=".ozon.ru")


def test_drop_client_clears_fingerprint() -> None:
    client = OzonHttpClient(
        api_base_url="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        category_path="/category/test/",
    )
    proxy = "http://proxy:8080"
    client._fingerprints[proxy] = _chrome_fingerprint()
    mock_http = MagicMock()
    client._clients[proxy] = mock_http
    client._drop_client(proxy)
    assert proxy not in client._fingerprints
    mock_http.close.assert_called_once()


def test_mask_proxy_hides_credentials() -> None:
    from marketplace_pipeline.infrastructure.http.ozon_http import _mask_proxy

    assert _mask_proxy(None) == "direct"
    assert _mask_proxy("http://user:pass@host:8080") == "host:8080"

