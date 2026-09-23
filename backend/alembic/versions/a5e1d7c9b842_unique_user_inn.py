"""Уникальность ИНН пользователя.

Revision ID: a5e1d7c9b842
Revises: f4d9b2a6c731
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5e1d7c9b842"
down_revision: Union[str, Sequence[str], None] = "f4d9b2a6c731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Канонизирует optional ИНН и добавляет уникальность реальных значений."""
    op.execute(
        sa.text(
            """
            DO $p93$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM users
                    WHERE btrim(coalesce(inn, '')) <> ''
                    GROUP BY btrim(inn)
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Обнаружены пользователи с одинаковым ИНН. '
                        'Разрешите дубликаты вручную перед повторным запуском миграции.'
                        USING ERRCODE = '23505';
                END IF;
            END
            $p93$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET inn = NULL
            WHERE inn IS NOT NULL
              AND btrim(inn) = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET inn = btrim(inn)
            WHERE inn IS NOT NULL
              AND inn <> btrim(inn)
            """
        )
    )
    op.create_index(
        "uq_users_inn",
        "users",
        ["inn"],
        unique=True,
    )


def downgrade() -> None:
    """Удаляет уникальный индекс ИНН без возврата неканонических пустых значений."""
    op.drop_index("uq_users_inn", table_name="users")
