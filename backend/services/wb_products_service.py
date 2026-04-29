from datetime import datetime, timezone
from uuid import UUID

from dateutil.parser import isoparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.wb_product import WbProduct

async def save_stocks(session: AsyncSession, user_id: UUID, token_id: UUID, data: list[dict]):
    stmt = insert(WbProduct).values([
        {
            "user_id": user_id,
            "token_id": token_id,

            "nm_id": item.get("nmId"),
            "warehouse_name": item.get("warehouseName"),

            "quantity": item.get("quantity") or 0,
            "in_way_to_client": item.get("inWayToClient") or 0,
            "in_way_from_client": item.get("inWayFromClient") or 0,

            "last_change_date": isoparse(item["lastChangeDate"]),
        }
        for item in data
    ])

    await session.execute(stmt)