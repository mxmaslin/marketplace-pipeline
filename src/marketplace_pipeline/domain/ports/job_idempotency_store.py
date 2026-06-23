from __future__ import annotations

from typing import Protocol


class JobIdempotencyStorePort(Protocol):
    """Maps client Idempotency-Key headers to pipeline job IDs."""

    def get(self, key: str) -> str | None:
        """Return job_id for key when present and not expired."""

    def reserve(self, key: str, job_id: str) -> bool:
        """Atomically reserve key → job_id. Returns False if key already taken."""
