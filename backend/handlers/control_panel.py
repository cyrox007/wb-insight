from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, Request

from core.logger import setup_logger
from core.dependencies import get_db_session
from services.tariff_service import get_tariffs_list
from services.user_service import get_user_count, get_user_list, get_user_by_uuid
from utils.responce_helps import response_success, response_error

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

@router.get('/users/{user_uuid}')
async def get_user(user_uuid: str, db_session: AsyncSession = Depends(get_db_session)):
    target_user = await get_user_by_uuid(db_session, user_uuid)
    del target_user.hashed_password # type: ignore
    return response_success(
        target_user=target_user
    )

@router.get('/tariffs')
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session)

    return response_success(tariffs=tariffs)



@router.post('/tariffs/create', status_code=status.HTTP_201_CREATED)
async def create_tariffs(request: Request):
    formdata = await request.json()
    
    code: str = formdata.get('code', None)
    name: str = formdata.get('name', None)
    description: str = formdata.get('description', '')
    price_raw: str = formdata.get('price_rub', "0.00")
    is_active: bool = formdata.get('is_active', False)

    if not code:
        return response_error(code='CODE_NONE', message='Code is required')

    if not name:
        return response_error(
            code='NAME_NONE',
            message='Name is required'
        )
    
    code = code.replace(' ', '_').upper()

    cleaned = str(price_raw).strip().replace(',', '.')
    price_rub = Decimal(cleaned).quantize(Decimal('0.00'))

    return response_success(tariff={
        'code': code,
        'name': name,
        'description': description,
        'price_rub': price_rub,
        'is_active': is_active
    })