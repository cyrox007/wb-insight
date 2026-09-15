"""add monthly revenue plans

Revision ID: a3c5e7f9b102
Revises: e71b8c2d4a90
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3c5e7f9b102"
down_revision: Union[str, Sequence[str], None] = "e71b8c2d4a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_revenue_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("revenue_target", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revenue_target > 0",
            name="ck_monthly_revenue_plan_positive_target",
        ),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "token_id",
            "month",
            name="uq_monthly_revenue_plan_user_token_month",
        ),
    )
    op.create_index(
        op.f("ix_monthly_revenue_plans_token_id"),
        "monthly_revenue_plans",
        ["token_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monthly_revenue_plans_user_id"),
        "monthly_revenue_plans",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_monthly_revenue_plans_user_month",
        "monthly_revenue_plans",
        ["user_id", "month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monthly_revenue_plans_user_month",
        table_name="monthly_revenue_plans",
    )
    op.drop_index(
        op.f("ix_monthly_revenue_plans_user_id"),
        table_name="monthly_revenue_plans",
    )
    op.drop_index(
        op.f("ix_monthly_revenue_plans_token_id"),
        table_name="monthly_revenue_plans",
    )
    op.drop_table("monthly_revenue_plans")
