
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.tariff_service import get_public_runtime_ready_tariffs
from utils.responce_helps import response_success


router = APIRouter(prefix='/dashboard/tariffs', tags=['Tariffs'])

@router.get('/', dependencies=[Depends(auth_middle)])
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_public_runtime_ready_tariffs(db_session)
    return response_success(tariffs=tariffs)