from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.wildberries.advertising_normalizer import flatten_fullstats_v3
from models.wb_advertising_stats import WbAdvertisingStats
from utils.batcher import chunks


BATCH_SIZE = 1000


async def save_advertising_fullstats(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    campaigns: list[dict[str, Any]],
) -> int:
    rows = flatten_fullstats_v3(campaigns, user_id, token_id)
    if not rows:
        return 0

    for batch in chunks(rows, BATCH_SIZE):
        stmt = insert(WbAdvertisingStats).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "token_id",
                "campaign_id",
                "nm_id",
                "date",
                "platform_type",
            ],
            set_={
                "product_name": stmt.excluded.product_name,
                "views": stmt.excluded.views,
                "clicks": stmt.excluded.clicks,
                "ctr": stmt.excluded.ctr,
                "cpc": stmt.excluded.cpc,
                "amount": stmt.excluded.amount,
                "added_to_cart": stmt.excluded.added_to_cart,
                "orders": stmt.excluded.orders,
                "canceled": stmt.excluded.canceled,
                "cr": stmt.excluded.cr,
                "shks": stmt.excluded.shks,
                "orders_amount": stmt.excluded.orders_amount,
                "avg_position": stmt.excluded.avg_position,
                "created_at": datetime.now(timezone.utc),
            },
        )
        await session.execute(stmt)

    return len(rows)
