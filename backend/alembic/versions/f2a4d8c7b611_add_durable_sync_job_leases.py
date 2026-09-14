"""add durable sync job leases

Revision ID: f2a4d8c7b611
Revises: e4d7a2c9f301
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a4d8c7b611"
down_revision: Union[str, Sequence[str], None] = "e4d7a2c9f301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_jobs",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "sync_jobs",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.alter_column("sync_jobs", "available_at", server_default=None)

    op.create_index(
        "ix_sync_jobs_available_at",
        "sync_jobs",
        ["available_at"],
        unique=False,
    )
    op.create_index(
        "ix_sync_jobs_lease_expires_at",
        "sync_jobs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_sync_jobs_pending_available",
        "sync_jobs",
        ["status", "available_at"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_sync_jobs_pending_available", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_lease_expires_at", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_available_at", table_name="sync_jobs")
    op.drop_column("sync_jobs", "lease_expires_at")
    op.drop_column("sync_jobs", "available_at")
    op.drop_column("sync_jobs", "attempt_count")
