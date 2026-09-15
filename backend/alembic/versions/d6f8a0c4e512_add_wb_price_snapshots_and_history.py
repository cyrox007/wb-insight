"""add WB price snapshots and history

Revision ID: d6f8a0c4e512
Revises: c5e7a9b2d304
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6f8a0c4e512"
down_revision: Union[str, Sequence[str], None] = "c5e7a9b2d304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wb_price_current",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.Column("size_id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_code", sa.String(length=200), nullable=True),
        sa.Column("tech_size_name", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("base_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("discounted_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("club_discounted_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("club_discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("editable_size_price", sa.Boolean(), nullable=False),
        sa.Column("is_bad_turnover", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_id",
            "nm_id",
            "size_id",
            name="uq_wb_price_current_account_nm_size",
        ),
    )
    op.create_index(op.f("ix_wb_price_current_user_id"), "wb_price_current", ["user_id"], unique=False)
    op.create_index(op.f("ix_wb_price_current_token_id"), "wb_price_current", ["token_id"], unique=False)
    op.create_index(op.f("ix_wb_price_current_nm_id"), "wb_price_current", ["nm_id"], unique=False)
    op.create_index(op.f("ix_wb_price_current_observed_at"), "wb_price_current", ["observed_at"], unique=False)
    op.create_index("ix_wb_price_current_user_nm", "wb_price_current", ["user_id", "nm_id"], unique=False)

    op.create_table(
        "wb_price_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.Column("size_id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_code", sa.String(length=200), nullable=True),
        sa.Column("tech_size_name", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("previous_base_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("base_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("previous_discounted_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("discounted_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("previous_club_discounted_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("club_discounted_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("previous_discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("previous_club_discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("club_discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wb_price_history_user_id"), "wb_price_history", ["user_id"], unique=False)
    op.create_index(op.f("ix_wb_price_history_token_id"), "wb_price_history", ["token_id"], unique=False)
    op.create_index(op.f("ix_wb_price_history_nm_id"), "wb_price_history", ["nm_id"], unique=False)
    op.create_index(op.f("ix_wb_price_history_changed_at"), "wb_price_history", ["changed_at"], unique=False)
    op.create_index("ix_wb_price_history_token_changed", "wb_price_history", ["token_id", "changed_at"], unique=False)
    op.create_index("ix_wb_price_history_nm_changed", "wb_price_history", ["nm_id", "changed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wb_price_history_nm_changed", table_name="wb_price_history")
    op.drop_index("ix_wb_price_history_token_changed", table_name="wb_price_history")
    op.drop_index(op.f("ix_wb_price_history_changed_at"), table_name="wb_price_history")
    op.drop_index(op.f("ix_wb_price_history_nm_id"), table_name="wb_price_history")
    op.drop_index(op.f("ix_wb_price_history_token_id"), table_name="wb_price_history")
    op.drop_index(op.f("ix_wb_price_history_user_id"), table_name="wb_price_history")
    op.drop_table("wb_price_history")

    op.drop_index("ix_wb_price_current_user_nm", table_name="wb_price_current")
    op.drop_index(op.f("ix_wb_price_current_observed_at"), table_name="wb_price_current")
    op.drop_index(op.f("ix_wb_price_current_nm_id"), table_name="wb_price_current")
    op.drop_index(op.f("ix_wb_price_current_token_id"), table_name="wb_price_current")
    op.drop_index(op.f("ix_wb_price_current_user_id"), table_name="wb_price_current")
    op.drop_table("wb_price_current")
