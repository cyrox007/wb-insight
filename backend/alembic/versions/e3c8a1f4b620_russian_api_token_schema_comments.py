"""Русские комментарии схемы реквизитов маркетплейса.

Revision ID: e3c8a1f4b620
Revises: e2b7c4d9a611
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3c8a1f4b620"
down_revision: Union[str, Sequence[str], None] = "e2b7c4d9a611"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Переводит комментарии столбцов api_tokens на русский язык."""
    op.alter_column(
        "api_tokens",
        "user_id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        comment="Владелец реквизитов кабинета маркетплейса",
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
        comment="Провайдер маркетплейса",
    )
    op.alter_column(
        "api_tokens",
        "token_type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        comment="Тип реквизитов или авторизации конкретного маркетплейса",
    )
    op.alter_column(
        "api_tokens",
        "external_account_id",
        existing_type=sa.String(length=255),
        existing_nullable=True,
        comment=(
            "Идентификатор продавца или кабинета на стороне маркетплейса; "
            "не является секретом"
        ),
    )
    op.alter_column(
        "api_tokens",
        "encrypted_token",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment="Зашифрованный секрет маркетплейса",
    )


def downgrade() -> None:
    """Удаляет добавленные русские комментарии без возврата английского текста."""
    op.alter_column(
        "api_tokens",
        "encrypted_token",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment=None,
        existing_comment="Зашифрованный секрет маркетплейса",
    )
    op.alter_column(
        "api_tokens",
        "external_account_id",
        existing_type=sa.String(length=255),
        existing_nullable=True,
        comment=None,
        existing_comment=(
            "Идентификатор продавца или кабинета на стороне маркетплейса; "
            "не является секретом"
        ),
    )
    op.alter_column(
        "api_tokens",
        "token_type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        comment=None,
        existing_comment="Тип реквизитов или авторизации конкретного маркетплейса",
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
        comment=None,
        existing_comment="Провайдер маркетплейса",
    )
    op.alter_column(
        "api_tokens",
        "user_id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        comment=None,
        existing_comment="Владелец реквизитов кабинета маркетплейса",
    )
