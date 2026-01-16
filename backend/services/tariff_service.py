from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from models.tariffs import TariffLimit, TariffPlan

logger = setup_logger(__name__)

async def insert_tariff(session: AsyncSession, tariff):
    new_tariff = TariffPlan(
        code = tariff['code'],
        name = tariff['name'],
        description = tariff['description'],
        price_rub = tariff['price_rub'],
        is_active = tariff['is_active']
    )

    try:
        session.add(new_tariff)
        await session.commit()
        await session.refresh(new_tariff)
        return new_tariff
    except Exception as e:
        logger.error(f"Error inserting tariff: {e}")
        await session.rollback()
        return None

async def get_tariffs_list(session: AsyncSession, 
                      offset: int = 0, limit: int = 10):
    query = select(TariffPlan).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()