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
    op.alter_column(
        "api_tokens",
        "user_id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        comment="Owner of the marketplace account credential",
        existing_comment="Привязка к пользователю",
    )
    op.alter_column(
        "api_tokens",
        "marketplace",
        existing_type=sa.Enum(
            "WILDBERRIES",
            "OZON",
            "YANDEX_MARKET",
            name="marketplace_enum",
        ),
        existing_nullable=False,
        comment="Marketplace provider",
        existing_comment="Маркетплейс",
    )
    op.alter_column(
        "api_tokens",
        "token_type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        comment="Marketplace-specific credential/auth type",
        existing_comment=None,
    )
    op.alter_column(
        "api_tokens",
        "encrypted_token",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment="Encrypted marketplace secret",
        existing_comment=None,
    )


def downgrade() -> None:
    op.alter_column(
        "api_tokens",
        "encrypted_token",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment=None,
        existing_comment="Encrypted marketplace secret",
    )
    op.alter_column(
        "api_tokens",
        "token_type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        comment=None,
        existing_comment="Marketplace-specific credential/auth type",
    )
    op.alter_column(
        "api_tokens",
        "marketplace",
        existing_type=sa.Enum(
            "WILDBERRIES",
            "OZON",
            "YANDEX_MARKET",
            name="marketplace_enum",
        ),
        existing_nullable=False,
        comment="Маркетплейс",
        existing_comment="Marketplace provider",
    )
    op.alter_column(
        "api_tokens",
        "user_id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        comment="Привязка к пользователю",
        existing_comment="Owner of the marketplace account credential",
    )
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
