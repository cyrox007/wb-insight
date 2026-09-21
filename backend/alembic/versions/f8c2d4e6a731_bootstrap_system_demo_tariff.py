"""bootstrap and protect the system demo tariff

Revision ID: f8c2d4e6a731
Revises: f7a1c3e5d902
Create Date: 2026-09-21 12:40:00

The demo tariff is runtime infrastructure, not a manually managed product row:
registration needs its FK and schedulers/quotas read its limits.
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f8c2d4e6a731"
down_revision: Union[str, Sequence[str], None] = "f7a1c3e5d902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEMO_LIMITS = {
    "wb_accounts": 1,
    "sync_frequency_hours": 1,
}


def upgrade() -> None:
    bind = op.get_bind()

    demo_rows = bind.execute(
        sa.text(
            """
            SELECT id, code
            FROM tariff_plans
            WHERE lower(code) = 'demo'
            ORDER BY created_at, id
            """
        )
    ).fetchall()

    if len(demo_rows) > 1:
        raise RuntimeError(
            "Multiple tariff_plans rows match demo case-insensitively; "
            "deduplicate them before applying this migration"
        )

    if demo_rows:
        demo_id = demo_rows[0].id
        bind.execute(
            sa.text(
                """
                UPDATE tariff_plans
                SET code = 'demo',
                    name = CASE WHEN btrim(name) = '' THEN 'Демо' ELSE name END,
                    description = CASE
                        WHEN btrim(coalesce(description, '')) = ''
                        THEN '7 дней бесплатного доступа'
                        ELSE description
                    END,
                    price_rub = 0.00,
                    is_active = true,
                    is_public = false,
                    updated_at = now()
                WHERE id = :demo_id
                """
            ),
            {"demo_id": demo_id},
        )
    else:
        demo_id = uuid4()
        bind.execute(
            sa.text(
                """
                INSERT INTO tariff_plans (
                    id,
                    code,
                    name,
                    description,
                    price_rub,
                    is_active,
                    is_public,
                    created_at,
                    updated_at
                )
                VALUES (
                    :demo_id,
                    'demo',
                    'Демо',
                    '7 дней бесплатного доступа',
                    0.00,
                    true,
                    false,
                    now(),
                    now()
                )
                """
            ),
            {"demo_id": demo_id},
        )

    for limit_type, limit_value in DEMO_LIMITS.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO tariff_limits (tariff_id, limit_type, limit_value)
                VALUES (:demo_id, :limit_type, :limit_value)
                ON CONFLICT (tariff_id, limit_type)
                DO UPDATE SET limit_value = CASE
                    WHEN tariff_limits.limit_value < 1 THEN EXCLUDED.limit_value
                    ELSE tariff_limits.limit_value
                END
                """
            ),
            {
                "demo_id": demo_id,
                "limit_type": limit_type,
                "limit_value": limit_value,
            },
        )


def downgrade() -> None:
    # Intentionally preserve the system tariff and its data. Existing
    # subscriptions may reference it, so deleting it during a downgrade would
    # either violate FK integrity or destroy runtime configuration.
    pass
