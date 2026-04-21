
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.tariff_service import get_tariffs_list
from utils.responce_helps import response_success


router = APIRouter(prefix='/dashboard/tariffs', tags=['Tariffs'])

@router.get('/', dependencies=[Depends(auth_middle)])
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session, only_active=True, only_public=True)
    return response_success(tariffs=tariffs)