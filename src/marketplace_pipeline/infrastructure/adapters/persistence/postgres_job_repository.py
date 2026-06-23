from __future__ import annotations

import logging
from datetime import UTC, datetime

from psycopg.rows import dict_row

from marketplace_pipeline.domain.models.pipeline_job import JobStatus, PipelineJob

logger = logging.getLogger(__name__)


class PostgresJobRepository:
    """Persistent job store for distributed async pipeline execution."""

    def __init__(self, database_url: str) -> None:
        import psycopg

        self._database_url = database_url
        self._psycopg = psycopg

    def _connect(self):
        return self._psycopg.connect(self._database_url, row_factory=dict_row)

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception as exc:
            logger.warning("Postgres job store ping failed: %s", exc)
            return False

    def create(self, job: PipelineJob) -> PipelineJob:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_jobs (
                    id, status, created_at, started_at, finished_at,
                    collection_target, collected_count, classified_count,
                    crm_tasks_count, output_path, error_message, correlation_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                self._to_row(job),
            )
            conn.commit()
        return job

    def get(self, job_id: str) -> PipelineJob | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_jobs WHERE id = %s", (job_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def update(self, job: PipelineJob) -> PipelineJob:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pipeline_jobs SET
                    status = %s, started_at = %s, finished_at = %s,
                    collected_count = %s, classified_count = %s,
                    crm_tasks_count = %s, output_path = %s, error_message = %s
                WHERE id = %s
                """,
                (
                    job.status.value,
                    job.started_at,
                    job.finished_at,
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
                "SELECT * FROM pipeline_jobs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _to_row(self, job: PipelineJob) -> tuple:
        return (
            job.id,
            job.status.value,
            job.created_at,
            job.started_at,
            job.finished_at,
            job.collection_target,
            job.collected_count,
            job.classified_count,
            job.crm_tasks_count,
            job.output_path,
            job.error_message,
            job.correlation_id,
        )

    def _from_row(self, row: dict) -> PipelineJob:
        return PipelineJob(
            id=row["id"],
            status=JobStatus(row["status"]),
            created_at=self._ensure_utc(row["created_at"]),
            started_at=self._optional_utc(row["started_at"]),
            finished_at=self._optional_utc(row["finished_at"]),
            collection_target=row["collection_target"],
            collected_count=row["collected_count"],
            classified_count=row["classified_count"],
            crm_tasks_count=row["crm_tasks_count"],
            output_path=row["output_path"],
            error_message=row["error_message"],
            correlation_id=row["correlation_id"],
        )

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @staticmethod
    def _optional_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return PostgresJobRepository._ensure_utc(value)
