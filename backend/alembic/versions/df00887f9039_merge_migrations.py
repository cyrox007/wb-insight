"""merge migrations

Revision ID: df00887f9039
Revises: fa0fae3a0187, fb776b45ca65
Create Date: 2026-04-08 10:56:14.429572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df00887f9039'
down_revision: Union[str, Sequence[str], None] = ('fa0fae3a0187', 'fb776b45ca65')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
