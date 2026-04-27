"""в таблицы для фильтрации появилось свойство токена

Revision ID: 186022a8f435
Revises: b632c3f97fb6
Create Date: 2026-04-27 13:28:26.731436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '186022a8f435'
down_revision: Union[str, Sequence[str], None] = 'b632c3f97fb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Сначала удаляем существующий внешний ключ
    op.drop_constraint(
        "wb_stocks_token_id_fkey",
        "wb_stocks",
        type_="foreignkey"
    )
    
    # 2. Изменяем тип api_tokens.id с VARCHAR на UUID
    op.alter_column('api_tokens', 'id',
               existing_type=sa.VARCHAR(length=36),
               type_=sa.UUID(),
               postgresql_using='id::uuid',
               existing_nullable=False)
    
    # 3. Изменяем тип wb_stocks.token_id с VARCHAR на UUID
    op.alter_column('wb_stocks', 'token_id',
               existing_type=sa.VARCHAR(length=36),
               type_=sa.UUID(),
               postgresql_using='token_id::uuid',
               existing_nullable=False)
    
    # 4. Добавляем колонку token_id в другие таблицы
    op.add_column('wb_realization_reports', 
                  sa.Column('token_id', sa.UUID(), 
                           server_default=sa.text('gen_random_uuid()'), 
                           nullable=False))
    op.create_index(op.f('ix_wb_realization_reports_token_id'), 
                   'wb_realization_reports', ['token_id'], unique=False)
    
    # 5. Теперь создаем внешний ключ, когда типы колонок совпадают
    op.create_foreign_key(
        "wb_stocks_token_id_fkey",
        "wb_stocks",
        "api_tokens",
        ["token_id"],
        ["id"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # В обратном порядке
    op.drop_constraint("wb_stocks_token_id_fkey", "wb_stocks", type_="foreignkey")
    
    op.drop_constraint(None, 'wb_realization_reports', type_='foreignkey')
    op.drop_index(op.f('ix_wb_realization_reports_token_id'), 
                 table_name='wb_realization_reports')
    op.drop_column('wb_realization_reports', 'token_id')
    
    op.alter_column('wb_stocks', 'token_id',
               existing_type=sa.UUID(),
               type_=sa.VARCHAR(length=36),
               existing_nullable=False)
    
    op.alter_column('api_tokens', 'id',
               existing_type=sa.UUID(),
               type_=sa.VARCHAR(length=36),
               existing_nullable=False)
    