from __future__ import annotations

from typing import Protocol


class ProxyQuotaCheckerPort(Protocol):
    """Checks upstream proxy provider quota before live Ozon collection."""

    def check_quota_available(self) -> None:
        """Raise ProxyQuotaExhaustedError when traffic or balance is insufficient."""
