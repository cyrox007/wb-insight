"""add WB operational orders and sales facts

Revision ID: c4e9b1d6a522
Revises: f2a4d8c7b611
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e9b1d6a522"
down_revision: Union[str, Sequence[str], None] = "f2a4d8c7b611"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_sync_states",
        sa.Column("source_cursor", sa.JSON(), nullable=True),
    )

    op.create_table(
        "wb_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("srid", sa.String(length=200), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_change_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warehouse_name", sa.String(length=200), nullable=True),
        sa.Column("warehouse_type", sa.String(length=100), nullable=True),
        sa.Column("country_name", sa.String(length=100), nullable=True),
        sa.Column("oblast_okrug_name", sa.String(length=200), nullable=True),
        sa.Column("region_name", sa.String(length=200), nullable=True),
        sa.Column("supplier_article", sa.String(length=200), nullable=True),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("tech_size", sa.String(length=100), nullable=True),
        sa.Column("income_id", sa.BigInteger(), nullable=True),
        sa.Column("is_supply", sa.Boolean(), nullable=True),
        sa.Column("is_realization", sa.Boolean(), nullable=True),
        sa.Column("total_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("spp", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("finished_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("price_with_disc", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("is_cancel", sa.Boolean(), nullable=False),
        sa.Column("cancel_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sticker", sa.String(length=100), nullable=True),
        sa.Column("g_number", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", "srid", name="uq_wb_order_account_srid"),
    )
    op.create_index("ix_wb_orders_user_id", "wb_orders", ["user_id"], unique=False)
    op.create_index("ix_wb_orders_token_id", "wb_orders", ["token_id"], unique=False)
    op.create_index("ix_wb_orders_order_date", "wb_orders", ["order_date"], unique=False)
    op.create_index("ix_wb_orders_last_change_date", "wb_orders", ["last_change_date"], unique=False)
    op.create_index("ix_wb_orders_nm_id", "wb_orders", ["nm_id"], unique=False)
    op.create_index("ix_wb_orders_user_date", "wb_orders", ["user_id", "order_date"], unique=False)
    op.create_index("ix_wb_orders_token_change", "wb_orders", ["token_id", "last_change_date"], unique=False)

    op.create_table(
        "wb_sales",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("sale_id", sa.String(length=100), nullable=False),
        sa.Column("srid", sa.String(length=200), nullable=True),
        sa.Column("sale_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_change_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warehouse_name", sa.String(length=200), nullable=True),
        sa.Column("warehouse_type", sa.String(length=100), nullable=True),
        sa.Column("country_name", sa.String(length=100), nullable=True),
        sa.Column("oblast_okrug_name", sa.String(length=200), nullable=True),
        sa.Column("region_name", sa.String(length=200), nullable=True),
        sa.Column("supplier_article", sa.String(length=200), nullable=True),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("tech_size", sa.String(length=100), nullable=True),
        sa.Column("income_id", sa.BigInteger(), nullable=True),
        sa.Column("is_supply", sa.Boolean(), nullable=True),
        sa.Column("is_realization", sa.Boolean(), nullable=True),
        sa.Column("total_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("spp", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("payment_sale_amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("for_pay", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("finished_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("price_with_disc", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("sticker", sa.String(length=100), nullable=True),
        sa.Column("g_number", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", "sale_id", name="uq_wb_sale_account_sale_id"),
    )
    op.create_index("ix_wb_sales_user_id", "wb_sales", ["user_id"], unique=False)
    op.create_index("ix_wb_sales_token_id", "wb_sales", ["token_id"], unique=False)
    op.create_index("ix_wb_sales_srid", "wb_sales", ["srid"], unique=False)
    op.create_index("ix_wb_sales_sale_date", "wb_sales", ["sale_date"], unique=False)
    op.create_index("ix_wb_sales_last_change_date", "wb_sales", ["last_change_date"], unique=False)
    op.create_index("ix_wb_sales_nm_id", "wb_sales", ["nm_id"], unique=False)
    op.create_index("ix_wb_sales_user_date", "wb_sales", ["user_id", "sale_date"], unique=False)
    op.create_index("ix_wb_sales_token_change", "wb_sales", ["token_id", "last_change_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wb_sales_token_change", table_name="wb_sales")
    op.drop_index("ix_wb_sales_user_date", table_name="wb_sales")
    op.drop_index("ix_wb_sales_nm_id", table_name="wb_sales")
    op.drop_index("ix_wb_sales_last_change_date", table_name="wb_sales")
    op.drop_index("ix_wb_sales_sale_date", table_name="wb_sales")
    op.drop_index("ix_wb_sales_srid", table_name="wb_sales")
    op.drop_index("ix_wb_sales_token_id", table_name="wb_sales")
    op.drop_index("ix_wb_sales_user_id", table_name="wb_sales")
    op.drop_table("wb_sales")

    op.drop_index("ix_wb_orders_token_change", table_name="wb_orders")
    op.drop_index("ix_wb_orders_user_date", table_name="wb_orders")
    op.drop_index("ix_wb_orders_nm_id", table_name="wb_orders")
    op.drop_index("ix_wb_orders_last_change_date", table_name="wb_orders")
    op.drop_index("ix_wb_orders_order_date", table_name="wb_orders")
    op.drop_index("ix_wb_orders_token_id", table_name="wb_orders")
    op.drop_index("ix_wb_orders_user_id", table_name="wb_orders")
    op.drop_table("wb_orders")

    op.drop_column("user_sync_states", "source_cursor")
