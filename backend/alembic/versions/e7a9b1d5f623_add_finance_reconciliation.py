"""add finance reconciliation tables

Revision ID: e7a9b1d5f623
Revises: d6f8a0c4e512
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a9b1d5f623"
down_revision: Union[str, Sequence[str], None] = "d6f8a0c4e512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wb_finance_report_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_finance_name", sa.String(length=300), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("create_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("report_type", sa.Integer(), nullable=True),
        sa.Column("retail_amount_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("for_pay_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("avg_sale_percent", sa.Numeric(10, 4), nullable=False),
        sa.Column("delivery_service_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_storage_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_acceptance_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("deduction_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("penalty_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("additional_payment_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("cashback_amount_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("cashback_discount_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("cashback_commission_change_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_schedule", sa.Numeric(18, 2), nullable=False),
        sa.Column("bank_payment_sum", sa.Numeric(18, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", "report_id", name="uq_wb_finance_report_account_report"),
    )
    op.create_index(op.f("ix_wb_finance_report_summaries_user_id"), "wb_finance_report_summaries", ["user_id"], unique=False)
    op.create_index(op.f("ix_wb_finance_report_summaries_token_id"), "wb_finance_report_summaries", ["token_id"], unique=False)
    op.create_index(op.f("ix_wb_finance_report_summaries_date_from"), "wb_finance_report_summaries", ["date_from"], unique=False)
    op.create_index(op.f("ix_wb_finance_report_summaries_date_to"), "wb_finance_report_summaries", ["date_to"], unique=False)
    op.create_index(op.f("ix_wb_finance_report_summaries_observed_at"), "wb_finance_report_summaries", ["observed_at"], unique=False)
    op.create_index("ix_wb_finance_report_user_period", "wb_finance_report_summaries", ["user_id", "date_from", "date_to"], unique=False)
    op.create_index("ix_wb_finance_report_token_period", "wb_finance_report_summaries", ["token_id", "date_from", "date_to"], unique=False)

    op.create_table(
        "wb_finance_balance_current",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("current_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("for_withdraw", sa.Numeric(18, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", name="uq_wb_finance_balance_account"),
    )
    op.create_index(op.f("ix_wb_finance_balance_current_user_id"), "wb_finance_balance_current", ["user_id"], unique=False)
    op.create_index(op.f("ix_wb_finance_balance_current_token_id"), "wb_finance_balance_current", ["token_id"], unique=False)
    op.create_index(op.f("ix_wb_finance_balance_current_observed_at"), "wb_finance_balance_current", ["observed_at"], unique=False)
    op.create_index("ix_wb_finance_balance_user", "wb_finance_balance_current", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wb_finance_balance_user", table_name="wb_finance_balance_current")
    op.drop_index(op.f("ix_wb_finance_balance_current_observed_at"), table_name="wb_finance_balance_current")
    op.drop_index(op.f("ix_wb_finance_balance_current_token_id"), table_name="wb_finance_balance_current")
    op.drop_index(op.f("ix_wb_finance_balance_current_user_id"), table_name="wb_finance_balance_current")
    op.drop_table("wb_finance_balance_current")

    op.drop_index("ix_wb_finance_report_token_period", table_name="wb_finance_report_summaries")
    op.drop_index("ix_wb_finance_report_user_period", table_name="wb_finance_report_summaries")
    op.drop_index(op.f("ix_wb_finance_report_summaries_observed_at"), table_name="wb_finance_report_summaries")
    op.drop_index(op.f("ix_wb_finance_report_summaries_date_to"), table_name="wb_finance_report_summaries")
    op.drop_index(op.f("ix_wb_finance_report_summaries_date_from"), table_name="wb_finance_report_summaries")
    op.drop_index(op.f("ix_wb_finance_report_summaries_token_id"), table_name="wb_finance_report_summaries")
    op.drop_index(op.f("ix_wb_finance_report_summaries_user_id"), table_name="wb_finance_report_summaries")
    op.drop_table("wb_finance_report_summaries")
