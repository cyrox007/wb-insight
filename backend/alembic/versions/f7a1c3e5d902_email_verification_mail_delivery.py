"""email verification and durable mail delivery

Revision ID: f7a1c3e5d902
Revises: e4a7b2c9d105
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f7a1c3e5d902"
down_revision: Union[str, Sequence[str], None] = "e4a7b2c9d105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент подтверждения владения текущим email",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "pending_email",
            sa.String(length=254),
            nullable=True,
            comment="Новый email, ожидающий подтверждения",
        ),
    )
    op.create_index("idx_users_pending_email", "users", ["pending_email"], unique=False)
    # Existing accounts pre-date mandatory verification and keep access after upgrade.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_tokens_user_id"), "email_verification_tokens", ["user_id"], unique=False)
    # mapped_column(unique=True, index=True) is represented by one unique index,
    # not by a redundant UNIQUE constraint plus an index.
    op.create_index(op.f("ix_email_verification_tokens_token_hash"), "email_verification_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_email_verification_tokens_expires_at"), "email_verification_tokens", ["expires_at"], unique=False)

    op.create_table(
        "mail_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("segment", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audience_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mail_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("safe_error_code", sa.String(length=96), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["mail_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_mail_messages_idempotency_key"),
    )
    op.create_index(op.f("ix_mail_messages_user_id"), "mail_messages", ["user_id"], unique=False)
    op.create_index(op.f("ix_mail_messages_recipient_email"), "mail_messages", ["recipient_email"], unique=False)
    op.create_index("ix_mail_messages_due", "mail_messages", ["status", "next_attempt_at", "created_at"], unique=False)
    op.create_index("ix_mail_messages_campaign_status", "mail_messages", ["campaign_id", "status"], unique=False)

    op.create_table(
        "mail_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False, server_default="unsubscribe"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_mail_suppressions_email"),
    )
    op.create_index(op.f("ix_mail_suppressions_user_id"), "mail_suppressions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_suppressions_user_id"), table_name="mail_suppressions")
    op.drop_table("mail_suppressions")
    op.drop_index("ix_mail_messages_campaign_status", table_name="mail_messages")
    op.drop_index("ix_mail_messages_due", table_name="mail_messages")
    op.drop_index(op.f("ix_mail_messages_recipient_email"), table_name="mail_messages")
    op.drop_index(op.f("ix_mail_messages_user_id"), table_name="mail_messages")
    op.drop_table("mail_messages")
    op.drop_table("mail_campaigns")
    op.drop_index(op.f("ix_email_verification_tokens_expires_at"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_index("idx_users_pending_email", table_name="users")
    op.drop_column("users", "pending_email")
    op.drop_column("users", "email_verified_at")
