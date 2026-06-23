from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, Field


class IdempotencyRecord(BaseModel):
    task_id: str
    title: str
    idempotency_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class IdempotencyStorePort(Protocol):
    def get(self, key: str) -> IdempotencyRecord | None: ...

    def put(self, key: str, record: IdempotencyRecord) -> None: ...
