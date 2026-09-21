"""add rich mail bodies and runtime SMTP provider config

Revision ID: d9e4a6b8c201
Revises: f8c2d4e6a731
Create Date: 2026-09-21 13:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d9e4a6b8c201"
down_revision: Union[str, Sequence[str], None] = "f8c2d4e6a731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mail_campaigns", sa.Column("body_html", sa.Text(), nullable=True))
    op.add_column("mail_messages", sa.Column("body_html", sa.Text(), nullable=True))

    op.create_table(
        "mail_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), server_default="587", nullable=False),
        sa.Column("from_email", sa.String(length=320), nullable=True),
        sa.Column("starttls", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="10", nullable=False),
        sa.Column("encrypted_secrets", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", name="uq_mail_provider_configs_provider"),
    )


def downgrade() -> None:
    op.drop_table("mail_provider_configs")
    op.drop_column("mail_messages", "body_html")
    op.drop_column("mail_campaigns", "body_html")
