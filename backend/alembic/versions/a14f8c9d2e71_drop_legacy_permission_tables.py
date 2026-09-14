"""drop legacy permission tables

Revision ID: a14f8c9d2e71
Revises: 93fe0c5c3f68
Create Date: 2026-09-14

Permissions are now fixed capabilities of system roles in core/access_control.py.
The user_roles table remains the only RBAC persistence required by the app.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a14f8c9d2e71"
down_revision: Union[str, Sequence[str], None] = "93fe0c5c3f68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")


def downgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("permissions.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_role_permissions",
        "role_permissions",
        ["role", "permission_id"],
        unique=False,
    )
