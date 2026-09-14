from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_product import WbProduct
from utils.batcher import chunks


async def save_products(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict],
) -> None:
    values = []
    for item in data:
        nm_id = item.get("nmID")
        title = item.get("title")
        if nm_id is None or not title:
            continue
        values.append(
            {
                "user_id": user_id,
                "token_id": token_id,
                "nm_id": nm_id,
                "title": title,
            }
        )

    if not values:
        return

    for batch in chunks(values, 500):
        stmt = insert(WbProduct).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_wb_product_account_nm",
            set_={
                "title": stmt.excluded.title,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await session.execute(stmt)
