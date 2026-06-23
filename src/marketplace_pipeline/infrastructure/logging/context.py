from __future__ import annotations

from contextvars import ContextVar, Token

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> Token[str | None]:
    return correlation_id_var.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    correlation_id_var.reset(token)
