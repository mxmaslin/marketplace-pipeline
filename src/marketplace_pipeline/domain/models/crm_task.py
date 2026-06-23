from __future__ import annotations

from pydantic import BaseModel


class CrmTaskRequest(BaseModel):
    title: str
    description: str


class CrmTaskOutcome(BaseModel):
    task_id: str
    title: str
    mocked: bool = False
    reused: bool = False
    idempotency_key: str | None = None
