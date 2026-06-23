"""Enriched product snapshots for horizontal scale.

Revision ID: 002
Revises: 001
Create Date: 2026-06-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE enriched_product_snapshots (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            meta JSONB NOT NULL,
            products JSONB NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS enriched_product_snapshots")
