"""Case-insensitive уникальность email пользователей.

Revision ID: f4d9b2a6c731
Revises: e3c8a1f4b620
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4d9b2a6c731"
down_revision: Union[str, Sequence[str], None] = "e3c8a1f4b620"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет уникальность email без учёта регистра с защитой существующих данных."""
    op.execute(
        sa.text(
            """
            DO $p91$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM users
                    GROUP BY lower(email)
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Обнаружены пользователи с email, совпадающими без учёта регистра. '
                        'Разрешите дубликаты вручную перед повторным запуском миграции.'
                        USING ERRCODE = '23505';
                END IF;
            END
            $p91$;
            """
        )
    )
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    """Удаляет case-insensitive индекс уникальности email."""
    op.drop_index("uq_users_email_lower", table_name="users")
