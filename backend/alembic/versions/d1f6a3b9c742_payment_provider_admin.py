"""payment provider admin configuration

Revision ID: d1f6a3b9c742
Revises: c8e5f1a2b934
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1f6a3b9c742"
down_revision: Union[str, Sequence[str], None] = "c8e5f1a2b934"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("api_base_url", sa.Text(), nullable=True),
        sa.Column("return_url", sa.Text(), nullable=True),
        sa.Column("fail_url", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False, server_default="643"),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, server_default="10"),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("encrypted_secrets", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "mode",
            name="uq_payment_provider_configs_provider_mode",
        ),
    )
    op.create_index(
        op.f("ix_payment_provider_configs_provider"),
        "payment_provider_configs",
        ["provider"],
        unique=False,
    )

    op.add_column(
        "payments",
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default="live",
            comment="Provider mode snapshot at payment creation: test or live",
        ),
    )
    op.execute("UPDATE payments SET mode = 'test' WHERE provider::text = 'fake'")


def downgrade() -> None:
    op.drop_column("payments", "mode")
    op.drop_index(op.f("ix_payment_provider_configs_provider"), table_name="payment_provider_configs")
    op.drop_table("payment_provider_configs")
