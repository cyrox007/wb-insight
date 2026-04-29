from datetime import datetime, timezone
from uuid import UUID

from dateutil.parser import isoparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.wb_product import WbProduct

async def save_products(session: AsyncSession, user_id: UUID, token_id: UUID, data: list[dict]):
    stmt = insert(WbProduct).values([
        {
            "user_id": user_id,
            "token_id": token_id,

            "nm_id": item.get("nmId"),
            "title": item.get("title")
        }
        for item in data
    ])

    await session.execute(stmt)