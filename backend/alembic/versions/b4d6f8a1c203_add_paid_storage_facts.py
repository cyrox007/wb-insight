"""add WB paid storage facts

Revision ID: b4d6f8a1c203
Revises: a3c5e7f9b102
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4d6f8a1c203"
down_revision: Union[str, Sequence[str], None] = "a3c5e7f9b102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wb_paid_storage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("source_task_id", sa.String(length=64), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("log_warehouse_coef", sa.Numeric(12, 4), nullable=True),
        sa.Column("office_id", sa.Integer(), nullable=True),
        sa.Column("warehouse", sa.String(length=255), nullable=True),
        sa.Column("warehouse_coef", sa.Numeric(12, 4), nullable=True),
        sa.Column("gi_id", sa.Integer(), nullable=True),
        sa.Column("chrt_id", sa.Integer(), nullable=True),
        sa.Column("size", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("vendor_code", sa.String(length=255), nullable=True),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Numeric(18, 6), nullable=True),
        sa.Column("calc_type", sa.String(length=255), nullable=True),
        sa.Column("warehouse_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("barcodes_count", sa.Integer(), nullable=True),
        sa.Column("pallet_place_code", sa.Integer(), nullable=True),
        sa.Column("pallet_count", sa.Numeric(18, 6), nullable=True),
        sa.Column("original_date", sa.Date(), nullable=True),
        sa.Column("loyalty_discount", sa.Numeric(12, 4), nullable=True),
        sa.Column("tariff_fix_date", sa.Date(), nullable=True),
        sa.Column("tariff_lower_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wb_paid_storage_user_id"), "wb_paid_storage", ["user_id"], unique=False)
    op.create_index(op.f("ix_wb_paid_storage_token_id"), "wb_paid_storage", ["token_id"], unique=False)
    op.create_index(op.f("ix_wb_paid_storage_date"), "wb_paid_storage", ["date"], unique=False)
    op.create_index(op.f("ix_wb_paid_storage_chrt_id"), "wb_paid_storage", ["chrt_id"], unique=False)
    op.create_index(op.f("ix_wb_paid_storage_nm_id"), "wb_paid_storage", ["nm_id"], unique=False)
    op.create_index("idx_wb_paid_storage_user_date", "wb_paid_storage", ["user_id", "date"], unique=False)
    op.create_index("idx_wb_paid_storage_token_date", "wb_paid_storage", ["token_id", "date"], unique=False)
    op.create_index("idx_wb_paid_storage_nm_date", "wb_paid_storage", ["nm_id", "date"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_wb_paid_storage_nm_date", table_name="wb_paid_storage")
    op.drop_index("idx_wb_paid_storage_token_date", table_name="wb_paid_storage")
    op.drop_index("idx_wb_paid_storage_user_date", table_name="wb_paid_storage")
    op.drop_index(op.f("ix_wb_paid_storage_nm_id"), table_name="wb_paid_storage")
    op.drop_index(op.f("ix_wb_paid_storage_chrt_id"), table_name="wb_paid_storage")
    op.drop_index(op.f("ix_wb_paid_storage_date"), table_name="wb_paid_storage")
    op.drop_index(op.f("ix_wb_paid_storage_token_id"), table_name="wb_paid_storage")
    op.drop_index(op.f("ix_wb_paid_storage_user_id"), table_name="wb_paid_storage")
    op.drop_table("wb_paid_storage")
