from __future__ import annotations

import logging
import threading
from pathlib import Path

from pydantic import BaseModel, Field

from marketplace_pipeline.domain.ports.idempotency_store import (
    IdempotencyRecord,
    IdempotencyStorePort,
)
from marketplace_pipeline.infrastructure.io.atomic import atomic_write_text
from marketplace_pipeline.infrastructure.io.file_lock import interprocess_file_lock

logger = logging.getLogger(__name__)


class _StoreSnapshot(BaseModel):
    records: dict[str, IdempotencyRecord] = Field(default_factory=dict)


class FileIdempotencyStore(IdempotencyStorePort):
    """Infrastructure adapter: JSON file persistence with locking and atomic writes."""

    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self._path = path
        self._lock_path = path.with_suffix(f"{path.suffix}.lock")
        self._enabled = enabled
        self._thread_lock = threading.Lock()
        self._snapshot = self._load()

    @classmethod
    def load(cls, path: Path) -> FileIdempotencyStore:
        return cls(path, enabled=True)

    def get(self, key: str) -> IdempotencyRecord | None:
        with self._thread_lock:
            self._reload_locked()
            return self._snapshot.records.get(key)

    def put(self, key: str, record: IdempotencyRecord) -> None:
        if not self._enabled:
            return
        with self._thread_lock:
            with interprocess_file_lock(self._lock_path):
                self._reload_locked()
                self._snapshot.records[key] = record
                self._persist_locked()

    def save(self, path: Path | None = None) -> None:
        if not self._enabled:
            return
        with self._thread_lock:
            with interprocess_file_lock(self._lock_path):
                if path is not None:
                    self._path = path
                    self._lock_path = path.with_suffix(f"{path.suffix}.lock")
                self._reload_locked()
                self._persist_locked()

    def _reload_locked(self) -> None:
        self._snapshot = self._load()

    def _load(self) -> _StoreSnapshot:
        if not self._enabled or not self._path.exists():
            return _StoreSnapshot()
        try:
            return _StoreSnapshot.model_validate_json(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load idempotency store %s: %s", self._path, exc)
            return _StoreSnapshot()

    def _persist_locked(self) -> None:
        atomic_write_text(self._path, self._snapshot.model_dump_json(indent=2))
