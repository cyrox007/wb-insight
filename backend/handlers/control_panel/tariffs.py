from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from services.tariff_service import get_tariffs_list, insert_tariff
from utils.responce_helps import response_error, response_success

router = APIRouter(prefix='/control-panel/tariffs', tags=['Control Panel'])

@router.get('/')
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session)

    return response_success(tariffs=tariffs)

@router.post('/create', status_code=status.HTTP_201_CREATED)
async def create_tariffs(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    formdata = await request.json()
    
    code: str = formdata.get('code', None)
    name: str = formdata.get('name', None)
    description: str = formdata.get('description', '')
    price_raw: str = formdata.get('price', "0.00")
    is_active: bool = formdata.get('isActive', False)

    if not code:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code='CODE_NONE', message='Code is required')

    if not name:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='NAME_NONE',
            message='Name is required'
        )
    
    code = code.replace(' ', '_').upper()

    cleaned = str(price_raw).strip().replace(',', '.')
    price_rub = Decimal(cleaned).quantize(Decimal('0.00'))

    tariff = await insert_tariff(db_session, {
        'code': code,
        'name': name,
        'description': description,
        'price_rub': price_rub,
        'is_active': is_active
    })

    if not tariff:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_EXISTS',
            message='Tariff with this code already exists'
        )

    return response_success(tariff=tariff)