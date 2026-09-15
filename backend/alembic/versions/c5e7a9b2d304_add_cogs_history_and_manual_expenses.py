"""add COGS history and manual expenses

Revision ID: c5e7a9b2d304
Revises: b4d6f8a1c203
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e7a9b2d304"
down_revision: Union[str, Sequence[str], None] = "b4d6f8a1c203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_cost_prices",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    # Existing snapshots were historically applied to every selected period in
    # the spreadsheet/current service. Preserve that behaviour during the
    # migration; only future edits become date-effective versions.
    op.execute(
        "UPDATE product_cost_prices "
        "SET effective_from = DATE '1970-01-01' "
        "WHERE effective_from IS NULL"
    )
    op.alter_column("product_cost_prices", "effective_from", nullable=False)
    op.create_index(
        "idx_product_cost_effective",
        "product_cost_prices",
        ["user_id", "nm_id", "effective_from"],
        unique=False,
    )

    op.create_table(
        "product_cost_price_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("seller_sku", sa.String(length=200), nullable=True),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("cost_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "nm_id",
            "effective_from",
            name="uq_product_cost_history_user_nm_effective",
        ),
    )
    op.create_index(op.f("ix_product_cost_price_history_user_id"), "product_cost_price_history", ["user_id"], unique=False)
    op.create_index(op.f("ix_product_cost_price_history_nm_id"), "product_cost_price_history", ["nm_id"], unique=False)
    op.create_index(op.f("ix_product_cost_price_history_effective_from"), "product_cost_price_history", ["effective_from"], unique=False)
    op.create_index(
        "idx_product_cost_history_lookup",
        "product_cost_price_history",
        ["user_id", "nm_id", "effective_from"],
        unique=False,
    )
    op.execute(
        "INSERT INTO product_cost_price_history "
        "(id, user_id, nm_id, effective_from, seller_sku, product_name, "
        "cost_price, currency, comment, created_at, updated_at) "
        "SELECT id, user_id, nm_id, effective_from, seller_sku, product_name, "
        "cost_price, currency, comment, created_at, updated_at "
        "FROM product_cost_prices"
    )

    op.create_table(
        "manual_expenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_manual_expense_positive_amount"),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manual_expenses_user_id"), "manual_expenses", ["user_id"], unique=False)
    op.create_index(op.f("ix_manual_expenses_token_id"), "manual_expenses", ["token_id"], unique=False)
    op.create_index(op.f("ix_manual_expenses_date"), "manual_expenses", ["date"], unique=False)
    op.create_index(op.f("ix_manual_expenses_nm_id"), "manual_expenses", ["nm_id"], unique=False)
    op.create_index("idx_manual_expenses_user_date", "manual_expenses", ["user_id", "date"], unique=False)
    op.create_index("idx_manual_expenses_token_date", "manual_expenses", ["token_id", "date"], unique=False)
    op.create_index("idx_manual_expenses_nm_date", "manual_expenses", ["nm_id", "date"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_manual_expenses_nm_date", table_name="manual_expenses")
    op.drop_index("idx_manual_expenses_token_date", table_name="manual_expenses")
    op.drop_index("idx_manual_expenses_user_date", table_name="manual_expenses")
    op.drop_index(op.f("ix_manual_expenses_nm_id"), table_name="manual_expenses")
    op.drop_index(op.f("ix_manual_expenses_date"), table_name="manual_expenses")
    op.drop_index(op.f("ix_manual_expenses_token_id"), table_name="manual_expenses")
    op.drop_index(op.f("ix_manual_expenses_user_id"), table_name="manual_expenses")
    op.drop_table("manual_expenses")

    op.drop_index("idx_product_cost_history_lookup", table_name="product_cost_price_history")
    op.drop_index(op.f("ix_product_cost_price_history_effective_from"), table_name="product_cost_price_history")
    op.drop_index(op.f("ix_product_cost_price_history_nm_id"), table_name="product_cost_price_history")
    op.drop_index(op.f("ix_product_cost_price_history_user_id"), table_name="product_cost_price_history")
    op.drop_table("product_cost_price_history")

    op.drop_index("idx_product_cost_effective", table_name="product_cost_prices")
    op.drop_column("product_cost_prices", "effective_from")
