from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_proxy_market_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not call live proxy.market unless they set the key explicitly."""
    monkeypatch.delenv("PROXY_MARKET_API_KEY", raising=False)
    monkeypatch.setenv("PROXY_MARKET_API_KEY", "")
