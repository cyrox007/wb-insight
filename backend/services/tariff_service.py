from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tariffs import TariffLimit, TariffPlan

async def insert_tariff(session, tariff):
    pass

async def get_tariffs_list(session: AsyncSession, 
                      offset: int = 0, limit: int = 10):
    query = select(TariffPlan).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.mappings().all()