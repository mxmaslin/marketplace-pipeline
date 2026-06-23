from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from marketplace_pipeline.domain.ports.idempotency_store import (
    IdempotencyRecord,
    IdempotencyStorePort,
)

logger = logging.getLogger(__name__)


class _StoreSnapshot(BaseModel):
    records: dict[str, IdempotencyRecord] = Field(default_factory=dict)


class FileIdempotencyStore(IdempotencyStorePort):
    """Infrastructure adapter: JSON file persistence for idempotency records."""

    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self._path = path
        self._enabled = enabled
        self._snapshot = self._load()

    @classmethod
    def load(cls, path: Path) -> FileIdempotencyStore:
        return cls(path, enabled=True)

    def get(self, key: str) -> IdempotencyRecord | None:
        return self._snapshot.records.get(key)

    def put(self, key: str, record: IdempotencyRecord) -> None:
        if not self._enabled:
            return
        self._snapshot.records[key] = record

    def save(self, path: Path | None = None) -> None:
        if not self._enabled:
            return
        if path is not None:
            self._path = path
        self._persist()

    def _load(self) -> _StoreSnapshot:
        if not self._enabled or not self._path.exists():
            return _StoreSnapshot()
        try:
            return _StoreSnapshot.model_validate_json(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load idempotency store %s: %s", self._path, exc)
            return _StoreSnapshot()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._snapshot.model_dump_json(indent=2), encoding="utf-8")
