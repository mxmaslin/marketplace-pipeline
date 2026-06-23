"""Initial pipeline_jobs schema.

Revision ID: 001
Revises:
Create Date: 2026-06-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pipeline_jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            collection_target INTEGER NOT NULL,
            collected_count INTEGER,
            classified_count INTEGER,
            crm_tasks_count INTEGER,
            output_path TEXT,
            error_message TEXT,
            correlation_id TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_pipeline_jobs_created_at ON pipeline_jobs (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pipeline_jobs_created_at")
    op.execute("DROP TABLE IF EXISTS pipeline_jobs")
