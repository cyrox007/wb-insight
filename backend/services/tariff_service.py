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

async def get_tariff_by_id(session: AsyncSession, tariff_id: str):
    query = select(TariffPlan).where(TariffPlan.id == tariff_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def update_tariff(session: AsyncSession, tariff: TariffPlan, tariff_data: dict):
    try:
        # Обновляем поля объекта
        for key, value in tariff_data.items():
            if hasattr(tariff, key):
                setattr(tariff, key, value)
        
        session.add(tariff)
        await session.commit()
        await session.refresh(tariff)  # обновить данные из БД (если есть триггеры)
        return tariff
    except Exception as e:
        logger.error(f"Error updating tariff: {e}")
        await session.rollback()
        return None