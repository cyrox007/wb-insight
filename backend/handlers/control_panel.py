from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from core.logger import setup_logger
from core.dependencies import get_db_session
from services.user_service import get_user_count, get_user_list
from utils.responce_helps import response_success

router = APIRouter(prefix='/control-panel', tags=['Control Panel'])
logger = setup_logger(__name__)


@router.get('/')
async def get_control_panel(db_session: AsyncSession = Depends(get_db_session)):
    user_count = await get_user_count(db_session)
    return response_success(
        user_count=user_count # передаем кол-во зарегестрированных юзеров
    )

@router.get('/users')
async def get_users(db_session: AsyncSession = Depends(get_db_session)):
    user_list = await get_user_list(db_session)
    return response_success(
        user_list=user_list
    )