"""Legacy idempotency re-exports."""

from marketplace_pipeline.domain.models.crm_task import CrmTaskRequest
from marketplace_pipeline.domain.ports.idempotency_store import IdempotencyRecord
from marketplace_pipeline.domain.services.idempotency_policy import (
    append_idempotency_marker,
    compute_task_idempotency_key,
    extract_idempotency_marker,
)
from marketplace_pipeline.infrastructure.adapters.crm.file_idempotency_store import (
    FileIdempotencyStore,
)

IdempotencyStore = FileIdempotencyStore


def compute_idempotency_key(payload: CrmTaskRequest) -> str:
    return compute_task_idempotency_key(payload)


__all__ = [
    "IdempotencyRecord",
    "IdempotencyStore",
    "append_idempotency_marker",
    "compute_idempotency_key",
    "extract_idempotency_marker",
]
