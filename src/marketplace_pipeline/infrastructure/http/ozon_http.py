from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError
from marketplace_pipeline.domain.services.proxy_prerequisites import is_proxy_quota_transport_error

logger = logging.getLogger(__name__)

_VIEWPORTS: tuple[tuple[int, int], ...] = (
    (1920, 1080),
    (1440, 900),
    (1366, 768),
    (390, 844),
)


@dataclass(frozen=True)
class BrowserProfile:
    name: str
    user_agent: str
    sec_ch_ua: str | None = None
    sec_ch_ua_mobile: str | None = None
    sec_ch_ua_platform: str | None = None


_BROWSER_PROFILES: tuple[BrowserProfile, ...] = (
    BrowserProfile(
        name="chrome",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"macOS"',
    ),
    BrowserProfile(
        name="chrome",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="121", "Google Chrome";v="121", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
    ),
    BrowserProfile(
        name="yandex",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 YaBrowser/24.3.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="122", "YaBrowser";v="24", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
    ),
    BrowserProfile(
        name="yandex",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 YaBrowser/24.3.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="122", "YaBrowser";v="24", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"macOS"',
    ),
    BrowserProfile(
        name="safari",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ),
    ),
    BrowserProfile(
        name="safari",
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
        ),
        sec_ch_ua_mobile="?1",
        sec_ch_ua_platform='"iOS"',
    ),
)


@dataclass(frozen=True)
class SessionFingerprint:
    profile: BrowserProfile
    viewport_width: int
    viewport_height: int


class OzonAntiBotError(Exception):
    """Ozon returned 403/429 or empty payload after anti-bot retries."""

    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ozon anti-bot block HTTP {status_code}: {detail[:200]}")


def parse_proxy_list(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]


def parse_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", maxsplit=1)
        cookies[name.strip()] = value.strip()
    return cookies


def browser_headers(
    *,
    fingerprint: SessionFingerprint,
    referer: str,
) -> dict[str, str]:
    profile = fingerprint.profile
    headers: dict[str, str] = {
        "User-Agent": profile.user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer,
        "Origin": "https://www.ozon.ru",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Viewport-Width": str(fingerprint.viewport_width),
    }
    if profile.sec_ch_ua is not None:
        headers["sec-ch-ua"] = profile.sec_ch_ua
    if profile.sec_ch_ua_mobile is not None:
        headers["sec-ch-ua-mobile"] = profile.sec_ch_ua_mobile
    elif fingerprint.viewport_width < 500:
        headers["sec-ch-ua-mobile"] = "?1"
    if profile.sec_ch_ua_platform is not None:
        headers["sec-ch-ua-platform"] = profile.sec_ch_ua_platform
    return headers


def _pick_viewport() -> tuple[int, int]:
    return random.choice(_VIEWPORTS)


def _pick_browser_profile() -> BrowserProfile:
    return random.choice(_BROWSER_PROFILES)


def _merge_response_cookies(client: httpx.Client, response: httpx.Response) -> None:
    for name, value in response.cookies.items():
        client.cookies.set(name, value, domain=".ozon.ru")


class OzonHttpClient:
    """Browser-like HTTP client for Ozon composer API with proxy/UA rotation."""

    def __init__(
        self,
        *,
        api_base_url: str,
        category_path: str,
        timeout: float = 30.0,
        max_retries: int = 5,
        base_delay: float = 1.0,
        request_delay_seconds: float = 0.0,
        request_delay_min_seconds: float | None = None,
        request_delay_max_seconds: float | None = None,
        follow_redirects: bool = True,
        warmup_session: bool = True,
        rotate_user_agents: bool = True,
        proxy_list: str = "",
        cookie_header: str = "",
        browser_profiles: tuple[BrowserProfile, ...] = _BROWSER_PROFILES,
    ) -> None:
        self._api_base_url = api_base_url
        self._category_path = category_path.rstrip("/") + "/"
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._base_delay = base_delay
        self._request_delay_seconds = max(0.0, request_delay_seconds)
        self._request_delay_min_seconds = request_delay_min_seconds
        self._request_delay_max_seconds = request_delay_max_seconds
        self._follow_redirects = follow_redirects
        self._warmup_session = warmup_session
        self._rotate_user_agents = rotate_user_agents
        self._proxies = parse_proxy_list(proxy_list)
        self._static_cookies = parse_cookie_header(cookie_header)
        self._browser_profiles = browser_profiles
        self._proxy_index = 0
        self._last_request_at = 0.0
        self._clients: dict[str | None, httpx.Client] = {}
        self._warmed_proxies: set[str | None] = set()
        self._fingerprints: dict[str | None, SessionFingerprint] = {}

    def close(self) -> None:
        for client in self._clients.values():
            client.close()
        self._clients.clear()
        self._warmed_proxies.clear()
        self._fingerprints.clear()

    def get_composer_json(self, *, page_path: str) -> dict[str, Any]:
        last_error = "unknown"
        attempts = self._max_retries * max(1, len(self._proxies) or 1)

        for attempt in range(attempts):
            if attempt:
                delay = min(60.0, self._base_delay * (2 ** (attempt - 1)))
                time.sleep(delay)

            proxy = self._next_proxy()
            fingerprint = self._fingerprint_for_proxy(proxy)
            try:
                payload = self._fetch_once(
                    page_path=page_path,
                    proxy=proxy,
                    fingerprint=fingerprint,
                )
                if payload.get("widgetStates"):
                    return payload
                last_error = "empty widgetStates in composer response"
                logger.warning("Ozon empty payload attempt %s/%s", attempt + 1, attempts)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (402, 407):
                    raise ProxyQuotaExhaustedError(
                        f"Proxy provider rejected request HTTP {exc.response.status_code}. "
                        "Check proxy.market traffic and balance."
                    ) from exc
                last_error = exc.response.text[:300]
                logger.warning(
                    "Ozon HTTP %s attempt %s/%s proxy=%s",
                    exc.response.status_code,
                    attempt + 1,
                    attempts,
                    _mask_proxy(proxy),
                )
                self._drop_client(proxy)
            except httpx.TransportError as exc:
                last_error = str(exc)
                if is_proxy_quota_transport_error(last_error):
                    raise ProxyQuotaExhaustedError(
                        "Proxy provider traffic or balance exhausted. "
                        f"Details: {last_error[:200]}"
                    ) from exc
                logger.warning(
                    "Ozon transport error attempt %s/%s: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                self._drop_client(proxy)

        raise OzonAntiBotError(status_code=403, detail=last_error)

    def _fetch_once(
        self,
        *,
        page_path: str,
        proxy: str | None,
        fingerprint: SessionFingerprint,
    ) -> dict[str, Any]:
        self._throttle()
        referer = f"https://www.ozon.ru{self._category_path}"
        client = self._client_for_proxy(proxy)
        headers = browser_headers(fingerprint=fingerprint, referer=referer)

        if self._warmup_session and proxy not in self._warmed_proxies:
            warm = client.get(referer, headers=headers)
            _merge_response_cookies(client, warm)
            if warm.status_code >= 400:
                logger.debug("Ozon warmup HTTP %s proxy=%s", warm.status_code, _mask_proxy(proxy))
            self._warmed_proxies.add(proxy)

        response = client.get(
            self._api_base_url,
            params={"url": page_path},
            headers=headers,
        )
        _merge_response_cookies(client, response)
        if response.status_code in (403, 429):
            response.raise_for_status()
        response.raise_for_status()
        return response.json()

    def _client_for_proxy(self, proxy: str | None) -> httpx.Client:
        if proxy not in self._clients:
            client_kwargs: dict[str, Any] = {
                "timeout": self._timeout,
                "follow_redirects": self._follow_redirects,
            }
            if proxy:
                client_kwargs["proxy"] = proxy
            client = httpx.Client(**client_kwargs)
            for name, value in self._static_cookies.items():
                client.cookies.set(name, value, domain=".ozon.ru")
            self._clients[proxy] = client
        return self._clients[proxy]

    def _drop_client(self, proxy: str | None) -> None:
        client = self._clients.pop(proxy, None)
        if client is not None:
            client.close()
        self._warmed_proxies.discard(proxy)
        self._fingerprints.pop(proxy, None)

    def _throttle(self) -> None:
        delay = self._next_request_delay()
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_at = time.monotonic()

    def _next_request_delay(self) -> float:
        min_delay = self._request_delay_min_seconds
        max_delay = self._request_delay_max_seconds
        if min_delay is not None and max_delay is not None and max_delay >= min_delay:
            return random.uniform(min_delay, max_delay)
        return self._request_delay_seconds

    def _next_proxy(self) -> str | None:
        if not self._proxies:
            return None
        proxy = self._proxies[self._proxy_index % len(self._proxies)]
        self._proxy_index += 1
        return proxy

    def _fingerprint_for_proxy(self, proxy: str | None) -> SessionFingerprint:
        if proxy in self._fingerprints:
            return self._fingerprints[proxy]
        if self._rotate_user_agents:
            profile = _pick_browser_profile()
            viewport = _pick_viewport()
        else:
            profile = self._browser_profiles[0]
            viewport = _VIEWPORTS[0]
        fingerprint = SessionFingerprint(
            profile=profile,
            viewport_width=viewport[0],
            viewport_height=viewport[1],
        )
        self._fingerprints[proxy] = fingerprint
        return fingerprint


def _mask_proxy(proxy: str | None) -> str:
    if not proxy:
        return "direct"
    if "@" in proxy:
        return proxy.split("@", maxsplit=1)[-1]
    return proxy


def build_ozon_http_client_from_settings(settings: object) -> OzonHttpClient:
    from marketplace_pipeline.infrastructure.config.settings import Settings

    if not isinstance(settings, Settings):
        raise TypeError("settings must be Settings")
    return OzonHttpClient(
        api_base_url=settings.ozon_api_base_url,
        category_path=settings.ozon_category_path,
        timeout=settings.ozon_request_timeout,
        max_retries=settings.http_max_retries,
        base_delay=settings.http_retry_base_delay,
        request_delay_seconds=settings.ozon_request_delay_seconds,
        request_delay_min_seconds=settings.ozon_request_delay_min_seconds,
        request_delay_max_seconds=settings.ozon_request_delay_max_seconds,
        follow_redirects=settings.ozon_follow_redirects,
        warmup_session=settings.ozon_warmup_session,
        rotate_user_agents=settings.ozon_rotate_user_agents,
        proxy_list=settings.ozon_proxy_list,
        cookie_header=settings.ozon_cookie,
    )
