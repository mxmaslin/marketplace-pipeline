from __future__ import annotations

import time
import uuid


class RedisSlidingWindowRateLimiter:
    """Distributed per-key sliding window rate limiter backed by Redis sorted sets."""

    def __init__(
        self,
        redis_url: str,
        *,
        limit_per_minute: int,
        key_prefix: str = "ratelimit",
    ) -> None:
        import redis

        self._limit = limit_per_minute
        self._key_prefix = key_prefix
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def allow(self, client_key: str) -> bool:
        if self._limit <= 0:
            return True
        now = time.time()
        window_start = now - 60.0
        redis_key = f"{self._key_prefix}:{client_key}"
        member = f"{now}:{uuid.uuid4().hex}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, 61)
        _, _, count, _ = pipe.execute()
        if count > self._limit:
            self._redis.zrem(redis_key, member)
            return False
        return True
