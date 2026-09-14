from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.wildberries.funnel_normalizer import flatten_sales_funnel_history
from models.wb_sales_funnel import WbSalesFunnelDaily
from utils.batcher import chunks


BATCH_SIZE = 1000


async def save_sales_funnel_history(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict[str, Any]],
) -> int:
    rows = flatten_sales_funnel_history(data, user_id, token_id)
    if not rows:
        return 0

    for batch in chunks(rows, BATCH_SIZE):
        stmt = insert(WbSalesFunnelDaily).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_wb_sales_funnel_account_nm_date",
            set_={
                "title": stmt.excluded.title,
                "vendor_code": stmt.excluded.vendor_code,
                "brand_name": stmt.excluded.brand_name,
                "subject_id": stmt.excluded.subject_id,
                "subject_name": stmt.excluded.subject_name,
                "currency": stmt.excluded.currency,
                "open_count": stmt.excluded.open_count,
                "cart_count": stmt.excluded.cart_count,
                "order_count": stmt.excluded.order_count,
                "order_sum": stmt.excluded.order_sum,
                "buyout_count": stmt.excluded.buyout_count,
                "buyout_sum": stmt.excluded.buyout_sum,
                "buyout_percent": stmt.excluded.buyout_percent,
                "add_to_cart_conversion": stmt.excluded.add_to_cart_conversion,
                "cart_to_order_conversion": stmt.excluded.cart_to_order_conversion,
                "add_to_wishlist_count": stmt.excluded.add_to_wishlist_count,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)

    return len(rows)
