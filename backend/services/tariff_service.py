from typing import Optional
from collections.abc import Sequence
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from models.tariffs import TariffLimit, TariffPlan

logger = setup_logger(__name__)

async def insert_tariff(session: AsyncSession, tariff) -> Optional[TariffPlan]:
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
                      offset: int = 0, limit: int = 10, **kwargs) -> Sequence[TariffPlan]:
    query = select(TariffPlan).offset(offset).limit(limit)
    if only_active := kwargs.get('only_active'):
        query = query.where(TariffPlan.is_active == only_active)
        
    result = await session.execute(query)
    return result.scalars().all()

async def get_tariff_by_id(session: AsyncSession, tariff_id: str):
    query = select(TariffPlan).where(TariffPlan.id == tariff_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def update_tariff(session: AsyncSession, tariff: TariffPlan, tariff_data: dict) -> Optional[TariffPlan]:
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
    

async def get_tariff_limits_by_id(session: AsyncSession, tariff_id: str) -> Sequence[TariffLimit]:
    query = select(TariffLimit).where(TariffLimit.tariff_id == tariff_id)
    result = await session.execute(query)
    return result.scalars().all()

async def delete_tariff_by_id(session: AsyncSession, tariff_id: str) -> bool:
    try:
        query = TariffPlan.delete().where(TariffPlan.id == tariff_id)
        await session.execute(query)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting tariff: {e}")
        await session.rollback()
        return False


""" async def insert_limit_by_tariff_id(session: AsyncSession, tariff_id: str, limit: dict) -> Optional[TariffLimit]:
    new_limit = TariffLimit(
        tariff_id = tariff_id,
        limit_type = limit['limit_type'],
        limit_value = limit['limit_value']
    )

    try:
        session.add(new_limit)
        await session.commit()
        await session.refresh(new_limit)
        return new_limit
    except Exception as e:
        logger.error(f"Error inserting limit: {e}")
        await session.rollback()
        return None """

async def upsert_limit(
    session: AsyncSession,
    tariff_id: str,
    limit: dict
) -> Optional[TariffLimit]:

    existing = await get_limit(session, tariff_id, limit['limit_type'])

    try:
        if existing:
            existing.limit_value = limit['limit_value']
            await session.commit()
            await session.refresh(existing)
            return existing

        new_limit = TariffLimit(
            tariff_id=tariff_id,
            limit_type=limit['limit_type'],
            limit_value=limit['limit_value']
        )

        session.add(new_limit)
        await session.commit()
        await session.refresh(new_limit)

        return new_limit

    except Exception as e:
        logger.error(f"Error upserting limit: {e}")
        await session.rollback()
        return None

async def get_limit(
    session: AsyncSession,
    tariff_id: str,
    limit_type: str
) -> Optional[TariffLimit]:
    query = select(TariffLimit).where(
        and_(
            TariffLimit.tariff_id == tariff_id,
            TariffLimit.limit_type == limit_type
        )
    )

    result = await session.execute(query)
    return result.scalar_one_or_none()

async def update_limit(session: AsyncSession, limit: TariffLimit, limit_data: dict) -> Optional[TariffLimit]:
    try:
        # Обновляем поля объекта
        for key, value in limit_data.items():
            if hasattr(limit, key):
                setattr(limit, key, value)
        session.add(limit)
        await session.commit()
        await session.refresh(limit)  # обновить данные из БД (если есть триггеры)
        return limit
    except Exception as e:
        logger.error(f"Error updating limit: {e}")
        await session.rollback()
        return None
    
async def delete_limit(session: AsyncSession, limit: TariffLimit) -> bool:
    try:
        await session.delete(limit)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting limit: {e}")
        await session.rollback()
        return False