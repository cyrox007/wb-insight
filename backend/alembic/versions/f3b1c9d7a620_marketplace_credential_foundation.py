"""marketplace credential foundation

Revision ID: f3b1c9d7a620
Revises: e7a9b1d5f623
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3b1c9d7a620"
down_revision: Union[str, Sequence[str], None] = "e7a9b1d5f623"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_tokens",
        sa.Column(
            "external_account_id",
            sa.String(length=255),
            nullable=True,
            comment="Marketplace-side seller/account identifier; never a secret",
        ),
    )
    op.create_index(
        op.f("ix_api_tokens_external_account_id"),
        "api_tokens",
        ["external_account_id"],
        unique=False,
    )
    op.alter_column(
        "api_tokens",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    # Credentials without a provider expiry (for example Ozon Api-Key) cannot
    # be represented by the legacy schema. Give them the issuance timestamp so
    # the NOT NULL constraint can be restored without an unsafe fabricated
    # future lifetime.
    op.execute(
        "UPDATE api_tokens SET expires_at = issued_at WHERE expires_at IS NULL"
    )
    op.alter_column(
        "api_tokens",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_index(
        op.f("ix_api_tokens_external_account_id"),
        table_name="api_tokens",
    )
    op.drop_column("api_tokens", "external_account_id")
