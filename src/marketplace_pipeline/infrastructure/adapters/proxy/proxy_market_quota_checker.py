from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError

logger = logging.getLogger(__name__)

_API_BASE = "https://api.dashboard.proxy.market"
_DASHBOARD_URL = "https://proxy.market"
_PACKAGES_PAGE_SIZE = 50


@dataclass(frozen=True)
class ProxyPackageQuota:
    package_id: int
    name: str
    total_bytes: int
    used_bytes: int
    is_active: bool

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.total_bytes - self.used_bytes)


def format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1_073_741_824:
        return f"{num_bytes / 1_073_741_824:.2f} GB"
    if num_bytes >= 1_048_576:
        return f"{num_bytes / 1_048_576:.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes} B"


class ProxyMarketQuotaChecker:
    """proxy.market API adapter: pre-flight traffic and balance checks."""

    def __init__(
        self,
        *,
        api_key: str,
        min_remaining_bytes: int = 1_048_576,
        min_balance: float = 0.0,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._min_remaining_bytes = min_remaining_bytes
        self._min_balance = min_balance
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def check_quota_available(self) -> None:
        try:
            packages = self._fetch_packages()
        except httpx.HTTPError as exc:
            logger.warning("PROXY_MARKET quota check skipped (API error): %s", exc)
            return

        active = [package for package in packages if package.is_active]
        if not active:
            raise ProxyQuotaExhaustedError(
                "PROXY_MARKET: no active traffic packages. "
                f"Top up at {_DASHBOARD_URL}"
            )

        depleted = [
            package
            for package in active
            if package.remaining_bytes < self._min_remaining_bytes
        ]
        if len(depleted) == len(active):
            details = "; ".join(
                (
                    f"'{package.name}' used {format_bytes(package.used_bytes)}/"
                    f"{format_bytes(package.total_bytes)}"
                )
                for package in active
            )
            raise ProxyQuotaExhaustedError(
                "PROXY_MARKET traffic exhausted "
                f"({details}). Top up at {_DASHBOARD_URL}"
            )

        balance = self._fetch_balance()
        if balance is not None and balance <= self._min_balance:
            prepaid_remaining = sum(package.remaining_bytes for package in active)
            if prepaid_remaining < self._min_remaining_bytes:
                raise ProxyQuotaExhaustedError(
                    f"PROXY_MARKET balance is {balance:.2f} and prepaid traffic is depleted. "
                    f"Top up at {_DASHBOARD_URL}"
                )

        logger.info(
            "PROXY_MARKET quota OK: %s active package(s), balance=%s",
            len(active),
            "n/a" if balance is None else f"{balance:.2f}",
        )

    def _fetch_packages(self) -> list[ProxyPackageQuota]:
        response = self._client.get(
            f"{_API_BASE}/dev-api/v2/packages/{self._api_key}",
            params={"page": 1, "perPage": _PACKAGES_PAGE_SIZE},
        )
        response.raise_for_status()
        payload = response.json()
        packages: list[ProxyPackageQuota] = []
        for item in payload.get("data", []):
            total = int(item.get("total") or 0)
            used = int(item.get("used") or 0)
            packages.append(
                ProxyPackageQuota(
                    package_id=int(item.get("id") or 0),
                    name=str(item.get("name") or "package"),
                    total_bytes=total,
                    used_bytes=used,
                    is_active=bool(item.get("is_active", True)),
                )
            )
        return packages

    def _fetch_balance(self) -> float | None:
        try:
            response = self._client.get(f"{_API_BASE}/dev-api/balance/{self._api_key}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PROXY_MARKET balance check failed: %s", exc)
            return None
        payload = response.json()
        try:
            return float(payload.get("balance", 0))
        except (TypeError, ValueError):
            return None
