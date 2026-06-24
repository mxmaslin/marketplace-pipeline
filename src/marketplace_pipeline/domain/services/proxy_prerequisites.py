from __future__ import annotations

from dataclasses import dataclass

from marketplace_pipeline.domain.ports.proxy_quota_checker import ProxyQuotaCheckerPort


@dataclass(frozen=True)
class ProxyPrerequisites:
    mock_parser: bool
    ozon_proxy_list: str
    proxy_market_api_key: str


def is_proxy_quota_transport_error(message: str) -> bool:
    lowered = message.lower()
    markers = (
        "traffic",
        "quota",
        "balance",
        "payment required",
        "no traffic",
        "out of traffic",
        "limit exceeded",
        "insufficient",
        "недостаточно",
        "трафик",
        "баланс",
    )
    return any(marker in lowered for marker in markers)


def validate_proxy_prerequisites(
    prerequisites: ProxyPrerequisites,
    *,
    quota_checker: ProxyQuotaCheckerPort | None = None,
) -> None:
    """Fail fast before live Ozon collection when proxy.market quota is exhausted."""
    if prerequisites.mock_parser:
        return
    if not prerequisites.proxy_market_api_key.strip():
        return
    if not prerequisites.ozon_proxy_list.strip():
        return
    if quota_checker is None:
        return
    quota_checker.check_quota_available()
