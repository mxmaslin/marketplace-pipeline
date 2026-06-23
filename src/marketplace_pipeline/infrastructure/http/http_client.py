from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"Rate limited: HTTP {response.status_code}")


class HttpClient:
    """HTTP client with exponential retries and explicit 429 handling."""

    def __init__(
        self,
        *,
        max_retries: int = 5,
        base_delay: float = 1.0,
        timeout: float = 30.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout

    def _build_retry(self) -> Any:
        return retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.base_delay, min=self.base_delay, max=60),
            retry=retry_if_exception_type((RateLimitError, httpx.TransportError)),
        )

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        @self._build_retry()
        def _request() -> httpx.Response:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=headers, params=params)
                if response.status_code == 429:
                    logger.warning("Received 429 from %s", url)
                    raise RateLimitError(response)
                response.raise_for_status()
                return response

        return _request()

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
    ) -> httpx.Response:
        @self._build_retry()
        def _request() -> httpx.Response:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=json)
                if response.status_code == 429:
                    logger.warning("Received 429 from %s", url)
                    raise RateLimitError(response)
                response.raise_for_status()
                return response

        return _request()
