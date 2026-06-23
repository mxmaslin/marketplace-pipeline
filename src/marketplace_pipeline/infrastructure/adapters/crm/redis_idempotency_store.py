from __future__ import annotations

import logging

from marketplace_pipeline.domain.ports.idempotency_store import (
    IdempotencyRecord,
    IdempotencyStorePort,
)

logger = logging.getLogger(__name__)

_KEY_PREFIX = "crm:idempotency:"


class RedisIdempotencyStore(IdempotencyStorePort):
    """Infrastructure adapter: Redis-backed idempotency (multi-node safe)."""

    def __init__(self, redis_url: str, *, enabled: bool = True) -> None:
        import redis

        self._enabled = enabled
        self._client = redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> IdempotencyRecord | None:
        if not self._enabled:
            return None
        raw = self._client.get(f"{_KEY_PREFIX}{key}")
        if raw is None:
            return None
        try:
            return IdempotencyRecord.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Invalid idempotency record for key %s: %s", key[:12], exc)
            return None

    def put(self, key: str, record: IdempotencyRecord) -> None:
        if not self._enabled:
            return
        self._client.set(f"{_KEY_PREFIX}{key}", record.model_dump_json())

    def save(self) -> None:
        """No-op: Redis writes are immediate."""

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception as exc:
            logger.warning("Redis idempotency ping failed: %s", exc)
            return False
