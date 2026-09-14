"""add daily WB sales funnel facts

Revision ID: e71b8c2d4a90
Revises: d9f3a5b0c744
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e71b8c2d4a90"
down_revision: Union[str, Sequence[str], None] = "d9f3a5b0c744"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wb_sales_funnel_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("vendor_code", sa.String(length=255), nullable=True),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False),
        sa.Column("cart_count", sa.Integer(), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("order_sum", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("buyout_count", sa.Integer(), nullable=False),
        sa.Column("buyout_sum", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("buyout_percent", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("add_to_cart_conversion", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("cart_to_order_conversion", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("add_to_wishlist_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_id",
            "nm_id",
            "date",
            name="uq_wb_sales_funnel_account_nm_date",
        ),
    )
    op.create_index(
        "idx_wb_sales_funnel_user_date",
        "wb_sales_funnel_daily",
        ["user_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_wb_sales_funnel_token_date",
        "wb_sales_funnel_daily",
        ["token_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_wb_sales_funnel_nm_date",
        "wb_sales_funnel_daily",
        ["nm_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wb_sales_funnel_daily_user_id"),
        "wb_sales_funnel_daily",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wb_sales_funnel_daily_token_id"),
        "wb_sales_funnel_daily",
        ["token_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wb_sales_funnel_daily_nm_id"),
        "wb_sales_funnel_daily",
        ["nm_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wb_sales_funnel_daily_date"),
        "wb_sales_funnel_daily",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wb_sales_funnel_daily_date"), table_name="wb_sales_funnel_daily")
    op.drop_index(op.f("ix_wb_sales_funnel_daily_nm_id"), table_name="wb_sales_funnel_daily")
    op.drop_index(op.f("ix_wb_sales_funnel_daily_token_id"), table_name="wb_sales_funnel_daily")
    op.drop_index(op.f("ix_wb_sales_funnel_daily_user_id"), table_name="wb_sales_funnel_daily")
    op.drop_index("idx_wb_sales_funnel_nm_date", table_name="wb_sales_funnel_daily")
    op.drop_index("idx_wb_sales_funnel_token_date", table_name="wb_sales_funnel_daily")
    op.drop_index("idx_wb_sales_funnel_user_date", table_name="wb_sales_funnel_daily")
    op.drop_table("wb_sales_funnel_daily")
