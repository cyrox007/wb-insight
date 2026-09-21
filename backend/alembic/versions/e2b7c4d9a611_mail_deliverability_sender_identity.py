"""mail deliverability sender identity

Revision ID: e2b7c4d9a611
Revises: d9e4a6b8c201
Create Date: 2026-09-21 14:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2b7c4d9a611"
down_revision: Union[str, Sequence[str], None] = "d9e4a6b8c201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mail_provider_configs", sa.Column("from_name", sa.String(length=160), nullable=True))
    op.add_column("mail_provider_configs", sa.Column("reply_to_email", sa.String(length=320), nullable=True))


def downgrade() -> None:
    op.drop_column("mail_provider_configs", "reply_to_email")
    op.drop_column("mail_provider_configs", "from_name")
