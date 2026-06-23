from __future__ import annotations

import hashlib

from marketplace_pipeline.domain.models.crm_task import CrmTaskRequest

IDEMPOTENCY_MARKER_PREFIX = "[pipeline:idempotency:"
IDEMPOTENCY_MARKER_SUFFIX = "]"


def compute_task_idempotency_key(task: CrmTaskRequest) -> str:
    canonical = f"{task.title.strip()}\n{task.description.strip()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_idempotency_marker(text: str, key: str) -> str:
    marker = f"{IDEMPOTENCY_MARKER_PREFIX}{key}{IDEMPOTENCY_MARKER_SUFFIX}"
    if marker in text:
        return text
    return f"{text.rstrip()}\n\n{marker}"


def extract_idempotency_marker(text: str) -> str | None:
    start = text.find(IDEMPOTENCY_MARKER_PREFIX)
    if start == -1:
        return None
    end = text.find(IDEMPOTENCY_MARKER_SUFFIX, start)
    if end == -1:
        return None
    return text[start + len(IDEMPOTENCY_MARKER_PREFIX) : end]
