"""Уникальность непустого ИНН без учёта внешних пробелов.

Идентификатор ревизии: a6d4f8c2e951
Предыдущая ревизия: f4d9b2a6c731
Дата: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6d4f8c2e951"
down_revision: Union[str, Sequence[str], None] = "f4d9b2a6c731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет уникальность нормализованного ИНН с защитой исторических данных."""
    op.alter_column(
        "users",
        "session_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default=sa.text("1"),
        existing_comment="Версия security session; increment отзывает ранее выданные JWT",
        comment="Версия сессии безопасности; увеличение отзывает ранее выданные JWT",
    )
    op.execute(
        sa.text(
            """
            DO $p94$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM users
                    WHERE inn IS NOT NULL
                      AND trim(inn) <> ''
                    GROUP BY trim(inn)
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Обнаружены пользователи с одинаковым ИНН после trim. '
                        'Разрешите дубликаты вручную перед повторным запуском миграции.'
                        USING ERRCODE = '23505';
                END IF;
            END
            $p94$;
            """
        )
    )
    op.create_index(
        "uq_users_inn_normalized",
        "users",
        [sa.text("TRIM(BOTH FROM inn)")],
        unique=True,
        postgresql_where=sa.text(
            "inn IS NOT NULL AND TRIM(BOTH FROM inn) <> ''"
        ),
    )


def downgrade() -> None:
    """Удаляет уникальный индекс и новый комментарий сессии."""
    op.drop_index("uq_users_inn_normalized", table_name="users")
    op.alter_column(
        "users",
        "session_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default=sa.text("1"),
        existing_comment="Версия сессии безопасности; увеличение отзывает ранее выданные JWT",
        comment=None,
    )
