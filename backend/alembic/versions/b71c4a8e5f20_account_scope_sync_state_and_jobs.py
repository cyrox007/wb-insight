"""scope sync state and jobs by marketplace token

Revision ID: b71c4a8e5f20
Revises: a14f8c9d2e71
Create Date: 2026-09-14

Legacy sync state was stored only per user + entity. Existing state is attached
to the user's oldest active credential; additional account states are created by
the scheduler after deploy. Existing sync jobs are transient and account-
ambiguous, so they are discarded during the migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b71c4a8e5f20"
down_revision: Union[str, Sequence[str], None] = "a14f8c9d2e71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_sync_states",
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # A legacy state represented all seller accounts of a user. Preserve its
    # cursor for one deterministic active credential; missing credentials get
    # fresh state rows from the scheduler after deployment.
    op.execute(
        """
        UPDATE user_sync_states AS state
        SET token_id = (
            SELECT token.id
            FROM api_tokens AS token
            WHERE token.user_id = state.user_id
              AND token.is_active = TRUE
              AND token.is_revoked = FALSE
            ORDER BY token.issued_at ASC, token.id ASC
            LIMIT 1
        )
        """
    )
    op.execute("DELETE FROM user_sync_states WHERE token_id IS NULL")

    # Jobs are short-lived queue records and had no reliable account identity.
    # Recreating them from state is safer than guessing the account.
    op.execute("DELETE FROM sync_jobs")

    op.drop_constraint("uq_sync_state", "user_sync_states", type_="unique")
    op.drop_index("uq_job_active", table_name="sync_jobs")

    op.create_foreign_key(
        "user_sync_states_token_id_fkey",
        "user_sync_states",
        "api_tokens",
        ["token_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "sync_jobs_token_id_fkey",
        "sync_jobs",
        "api_tokens",
        ["token_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("user_sync_states", "token_id", nullable=False)
    op.alter_column("sync_jobs", "token_id", nullable=False)

    op.create_index(
        "ix_user_sync_states_token_id",
        "user_sync_states",
        ["token_id"],
        unique=False,
    )
    op.create_index(
        "ix_sync_jobs_token_id",
        "sync_jobs",
        ["token_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_sync_state",
        "user_sync_states",
        ["user_id", "token_id", "entity"],
    )
    op.create_index(
        "uq_job_active",
        "sync_jobs",
        ["token_id", "entity"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    # Multiple account-scoped rows cannot be represented by the legacy schema.
    # Keep the oldest state per user/entity before restoring its unique key.
    op.execute(
        """
        DELETE FROM user_sync_states AS newer
        USING user_sync_states AS older
        WHERE newer.user_id = older.user_id
          AND newer.entity = older.entity
          AND (
                newer.created_at > older.created_at
                OR (newer.created_at = older.created_at AND newer.id > older.id)
          )
        """
    )
    op.execute("DELETE FROM sync_jobs")

    op.drop_index("uq_job_active", table_name="sync_jobs")
    op.drop_constraint("uq_sync_state", "user_sync_states", type_="unique")
    op.drop_index("ix_sync_jobs_token_id", table_name="sync_jobs")
    op.drop_index("ix_user_sync_states_token_id", table_name="user_sync_states")
    op.drop_constraint("sync_jobs_token_id_fkey", "sync_jobs", type_="foreignkey")
    op.drop_constraint(
        "user_sync_states_token_id_fkey",
        "user_sync_states",
        type_="foreignkey",
    )
    op.drop_column("sync_jobs", "token_id")
    op.drop_column("user_sync_states", "token_id")

    op.create_unique_constraint(
        "uq_sync_state",
        "user_sync_states",
        ["user_id", "entity"],
    )
    op.create_index(
        "uq_job_active",
        "sync_jobs",
        ["user_id", "entity"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
