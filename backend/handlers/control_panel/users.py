from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from services.user_service import get_user_by_uuid, get_user_list
from utils.responce_helps import response_success


router = APIRouter(prefix='/control-panel/users', tags=['Control Panel'])

@router.get('/')
async def get_users(db_session: AsyncSession = Depends(get_db_session)):
    user_list = await get_user_list(db_session)
    return response_success(
        user_list=user_list
    )

@router.get('/{user_uuid}')
async def get_user(user_uuid: str, db_session: AsyncSession = Depends(get_db_session)):
    target_user = await get_user_by_uuid(db_session, user_uuid)
    del target_user.hashed_password # type: ignore
    return response_success(
        target_user=target_user
    )