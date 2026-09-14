"""align current WB finance and stock contracts

Revision ID: e4d7a2c9f301
Revises: b71c4a8e5f20
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4d7a2c9f301"
down_revision: Union[str, Sequence[str], None] = "b71c4a8e5f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Current WB stock analytics returns one row per size (chrtId) and warehouse.
    op.add_column("wb_stocks", sa.Column("chrt_id", sa.Integer(), nullable=True))
    op.add_column("wb_stocks", sa.Column("region_name", sa.String(length=100), nullable=True))
    op.create_index("ix_wb_stocks_chrt_id", "wb_stocks", ["chrt_id"], unique=False)
    op.create_index("ix_wb_stocks_region_name", "wb_stocks", ["region_name"], unique=False)
    op.alter_column(
        "wb_stocks",
        "last_change_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.drop_constraint("uq_wb_stock_ui", "wb_stocks", type_="unique")
    op.create_unique_constraint(
        "uq_wb_stock_ui",
        "wb_stocks",
        ["token_id", "nm_id", "chrt_id", "warehouse_id"],
    )

    # rrdId identifies a report row inside a seller account. It must not make
    # two different marketplace credentials conflict with each other.
    op.execute(
        "ALTER TABLE wb_realization_reports "
        "DROP CONSTRAINT IF EXISTS wb_realization_reports_rrd_id_key"
    )
    op.execute("DROP INDEX IF EXISTS uq_wb_realization_rrd_id")
    op.execute("DROP INDEX IF EXISTS ix_wb_realization_reports_rrd_id")
    op.create_index(
        "ix_wb_realization_reports_rrd_id",
        "wb_realization_reports",
        ["rrd_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_wb_realization_token_rrd",
        "wb_realization_reports",
        ["token_id", "rrd_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_wb_realization_token_rrd",
        "wb_realization_reports",
        type_="unique",
    )
    op.drop_index("ix_wb_realization_reports_rrd_id", table_name="wb_realization_reports")
    op.create_index(
        "ix_wb_realization_reports_rrd_id",
        "wb_realization_reports",
        ["rrd_id"],
        unique=True,
    )

    op.drop_constraint("uq_wb_stock_ui", "wb_stocks", type_="unique")
    op.create_unique_constraint(
        "uq_wb_stock_ui",
        "wb_stocks",
        ["token_id", "nm_id", "warehouse_id"],
    )
    op.execute(
        "UPDATE wb_stocks SET last_change_date = "
        "COALESCE(last_change_date, updated_at, now())"
    )
    op.alter_column(
        "wb_stocks",
        "last_change_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_index("ix_wb_stocks_region_name", table_name="wb_stocks")
    op.drop_index("ix_wb_stocks_chrt_id", table_name="wb_stocks")
    op.drop_column("wb_stocks", "region_name")
    op.drop_column("wb_stocks", "chrt_id")
