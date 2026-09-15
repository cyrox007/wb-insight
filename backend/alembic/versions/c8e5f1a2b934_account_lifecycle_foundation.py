"""account lifecycle foundation

Revision ID: c8e5f1a2b934
Revises: b7d4e6f8a921
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8e5f1a2b934"
down_revision: Union[str, Sequence[str], None] = "b7d4e6f8a921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deactivation_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "subscriptions",
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("subscriptions", sa.Column("cancel_reason", sa.Text(), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_active",
        "password_reset_tokens",
        ["user_id", "expires_at", "used_at"],
    )

    op.create_table(
        "account_lifecycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_lifecycle_events_user_id", "account_lifecycle_events", ["user_id"])
    op.create_index("ix_account_lifecycle_events_actor_user_id", "account_lifecycle_events", ["actor_user_id"])
    op.create_index("ix_account_lifecycle_events_event_type", "account_lifecycle_events", ["event_type"])
    op.create_index("ix_account_lifecycle_events_created_at", "account_lifecycle_events", ["created_at"])
    op.create_index(
        "ix_account_lifecycle_user_created",
        "account_lifecycle_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_lifecycle_user_created", table_name="account_lifecycle_events")
    op.drop_index("ix_account_lifecycle_events_created_at", table_name="account_lifecycle_events")
    op.drop_index("ix_account_lifecycle_events_event_type", table_name="account_lifecycle_events")
    op.drop_index("ix_account_lifecycle_events_actor_user_id", table_name="account_lifecycle_events")
    op.drop_index("ix_account_lifecycle_events_user_id", table_name="account_lifecycle_events")
    op.drop_table("account_lifecycle_events")

    op.drop_index("ix_password_reset_tokens_active", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_column("subscriptions", "cancel_reason")
    op.drop_column("subscriptions", "cancel_requested_at")
    op.drop_column("subscriptions", "cancel_at_period_end")
    op.drop_column("users", "retention_until")
    op.drop_column("users", "deactivation_reason")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "session_version")
