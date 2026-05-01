from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.wb_product import WbProduct

async def save_products(session: AsyncSession, user_id: UUID, token_id: UUID, data: list[dict]):
    # Фильтруем товары, у которых отсутствует nmId (артикул)
    # Это необходимо, так как поле nm_id в БД обязательное (NOT NULL)
    valid_items = []
    skipped_count = 0

    for item in data:
        nm_id = item.get("nmID")
        if nm_id is None:
            skipped_count += 1
            continue
        valid_items.append({
            "user_id": user_id,
            "token_id": token_id,
            "nm_id": nm_id,
            "title": item.get("title")
        })

    if skipped_count > 0:
        from core.logger import setup_logger
        logger = setup_logger(__name__, "wb_api_processor.log")
        logger.warning(f"[PRODUCTS] Skipped {skipped_count} items without nmId")

    if not valid_items:
        return

    stmt = insert(WbProduct).values(valid_items)

    await session.execute(stmt)