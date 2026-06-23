from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_KEY_PREFIX = "job:idempotency:"


class RedisJobIdempotencyStore:
    """Redis-backed job submit idempotency (multi-node safe)."""

    def __init__(self, redis_url: str, *, ttl_seconds: int = 86_400) -> None:
        import redis

        self._ttl_seconds = ttl_seconds
        self._client = redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._client.get(f"{_KEY_PREFIX}{key}")

    def reserve(self, key: str, job_id: str) -> bool:
        return bool(
            self._client.set(
                f"{_KEY_PREFIX}{key}",
                job_id,
                nx=True,
                ex=self._ttl_seconds,
            )
        )

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception as exc:
            logger.warning("Redis job idempotency ping failed: %s", exc)
            return False
