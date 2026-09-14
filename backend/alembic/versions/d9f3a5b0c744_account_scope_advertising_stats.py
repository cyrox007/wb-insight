"""account scope WB advertising facts

Revision ID: d9f3a5b0c744
Revises: c4e9b1d6a522
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9f3a5b0c744"
down_revision: Union[str, Sequence[str], None] = "c4e9b1d6a522"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wb_advertising_stats",
        sa.Column("canceled", sa.Integer(), nullable=True),
    )
    op.add_column(
        "wb_advertising_stats",
        sa.Column("currency", sa.String(length=16), nullable=True),
    )
    op.execute("UPDATE wb_advertising_stats SET canceled = 0 WHERE canceled IS NULL")
    op.alter_column(
        "wb_advertising_stats",
        "canceled",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.execute(
        "UPDATE wb_advertising_stats SET platform_type = 0 "
        "WHERE platform_type IS NULL"
    )
    op.alter_column(
        "wb_advertising_stats",
        "platform_type",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Old uniqueness was user-scoped and NULL platform values could coexist.
    # Keep the newest legacy row for the new marketplace-account identity.
    op.execute(
        "DELETE FROM wb_advertising_stats WHERE id IN ("
        "  SELECT id FROM ("
        "    SELECT id, ROW_NUMBER() OVER ("
        "      PARTITION BY token_id, campaign_id, nm_id, date, platform_type "
        "      ORDER BY created_at DESC, id DESC"
        "    ) AS rn FROM wb_advertising_stats"
        "  ) ranked WHERE rn > 1"
        ")"
    )

    op.drop_index("idx_wb_adv_unique", table_name="wb_advertising_stats")
    op.create_index(
        "idx_wb_adv_unique",
        "wb_advertising_stats",
        ["token_id", "campaign_id", "nm_id", "date", "platform_type"],
        unique=True,
    )
    op.create_index(
        "idx_wb_adv_token_date",
        "wb_advertising_stats",
        ["token_id", "date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_wb_adv_token_date", table_name="wb_advertising_stats")
    op.drop_index("idx_wb_adv_unique", table_name="wb_advertising_stats")

    # Multiple account rows can collapse to one row under the legacy user key.
    op.execute(
        "DELETE FROM wb_advertising_stats WHERE id IN ("
        "  SELECT id FROM ("
        "    SELECT id, ROW_NUMBER() OVER ("
        "      PARTITION BY user_id, campaign_id, nm_id, date, platform_type "
        "      ORDER BY created_at DESC, id DESC"
        "    ) AS rn FROM wb_advertising_stats"
        "  ) ranked WHERE rn > 1"
        ")"
    )
    op.create_index(
        "idx_wb_adv_unique",
        "wb_advertising_stats",
        ["user_id", "campaign_id", "nm_id", "date", "platform_type"],
        unique=True,
    )
    op.alter_column(
        "wb_advertising_stats",
        "platform_type",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_column("wb_advertising_stats", "currency")
    op.drop_column("wb_advertising_stats", "canceled")
