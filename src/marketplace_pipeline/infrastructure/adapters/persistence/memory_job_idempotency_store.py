from __future__ import annotations

import threading
import time


class MemoryJobIdempotencyStore:
    """In-process idempotency store for single-node API deployments."""

    def __init__(self, *, ttl_seconds: int = 86_400) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._get_unlocked(key)

    def reserve(self, key: str, job_id: str) -> bool:
        with self._lock:
            self._purge_expired_unlocked()
            if key in self._entries:
                return False
            self._entries[key] = (job_id, time.monotonic() + self._ttl_seconds)
            return True

    def _get_unlocked(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        job_id, expires_at = entry
        if time.monotonic() > expires_at:
            del self._entries[key]
            return None
        return job_id

    def _purge_expired_unlocked(self) -> None:
        now = time.monotonic()
        expired = [key for key, (_, exp) in self._entries.items() if now > exp]
        for key in expired:
            del self._entries[key]
