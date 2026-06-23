from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    collection_target INTEGER NOT NULL,
    collected_count INTEGER,
    classified_count INTEGER,
    crm_tasks_count INTEGER,
    output_path TEXT,
    error_message TEXT,
    correlation_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_created_at ON pipeline_jobs(created_at DESC);
"""


class SqliteJobRepository:
    """Persistent job store for async pipeline execution."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def create(self, job: PipelineJob) -> PipelineJob:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_jobs (
                    id, status, created_at, started_at, finished_at,
                    collection_target, collected_count, classified_count,
                    crm_tasks_count, output_path, error_message, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(job),
            )
            conn.commit()
        return job

    def get(self, job_id: str) -> PipelineJob | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def update(self, job: PipelineJob) -> PipelineJob:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pipeline_jobs SET
                    status = ?, started_at = ?, finished_at = ?,
                    collected_count = ?, classified_count = ?,
                    crm_tasks_count = ?, output_path = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    job.status.value,
                    self._dt(job.started_at),
                    self._dt(job.finished_at),
                    job.collected_count,
                    job.classified_count,
                    job.crm_tasks_count,
                    job.output_path,
                    job.error_message,
                    job.id,
                ),
            )
            conn.commit()
        return job

    def list_recent(self, limit: int = 20) -> list[PipelineJob]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _dt(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    def _to_row(self, job: PipelineJob) -> tuple:
        return (
            job.id,
            job.status.value,
            job.created_at.isoformat(),
            self._dt(job.started_at),
            self._dt(job.finished_at),
            job.collection_target,
            job.collected_count,
            job.classified_count,
            job.crm_tasks_count,
            job.output_path,
            job.error_message,
            job.correlation_id,
        )

    def _from_row(self, row: sqlite3.Row) -> PipelineJob:
        return PipelineJob(
            id=row["id"],
            status=JobStatus(row["status"]),
            created_at=self._parse_dt(row["created_at"]) or datetime.now(tz=UTC),
            started_at=self._parse_dt(row["started_at"]),
            finished_at=self._parse_dt(row["finished_at"]),
            collection_target=row["collection_target"],
            collected_count=row["collected_count"],
            classified_count=row["classified_count"],
            crm_tasks_count=row["crm_tasks_count"],
            output_path=row["output_path"],
            error_message=row["error_message"],
            correlation_id=row["correlation_id"],
        )
