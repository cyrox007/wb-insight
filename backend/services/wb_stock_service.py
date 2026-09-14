from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_stock import WbStock
from utils.batcher import chunks


async def save_stocks(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict],
) -> None:
    if not data:
        return

    values = [
        {
            "user_id": user_id,
            "token_id": token_id,
            "nm_id": item.get("nmId"),
            "chrt_id": item.get("chrtId"),
            "warehouse_id": item.get("warehouseId"),
            "warehouse_name": item.get("warehouseName"),
            "region_name": item.get("regionName"),
            "quantity": item.get("quantity") or 0,
            "in_way_to_client": item.get("inWayToClient") or 0,
            "in_way_from_client": item.get("inWayFromClient") or 0,
        }
        for item in data
    ]

    for batch in chunks(values, 500):
        stmt = insert(WbStock).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_wb_stock_ui",
            set_={
                "warehouse_name": stmt.excluded.warehouse_name,
                "region_name": stmt.excluded.region_name,
                "quantity": stmt.excluded.quantity,
                "in_way_to_client": stmt.excluded.in_way_to_client,
                "in_way_from_client": stmt.excluded.in_way_from_client,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await session.execute(stmt)
