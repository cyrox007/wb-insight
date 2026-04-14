from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from services.tariff_service import (
    get_tariffs_list, 
    insert_tariff, 
    get_tariff_by_id, 
    update_tariff, 
    get_tariff_limits_by_id, 
    delete_tariff_by_id,
    upsert_limit,
    # insert_limit_by_tariff_id,
    get_limit,
    update_limit,
    delete_limit
)
from utils.responce_helps import response_error, response_success

router = APIRouter(prefix='/control-panel/tariffs', tags=['Tariffs'])

@router.get('/')
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session)

    return response_success(tariffs=tariffs)

@router.get('/{tariff_id}')
async def get_tariff(tariff_id: str, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    tariff = await get_tariff_by_id(db_session, tariff_id)

    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='TARIFF_NOT_FOUND',
            message='Tariff not found'
        )

    limits = await get_tariff_limits_by_id(db_session, str(tariff.id))
    
    return response_success(
        tariff=tariff,
        limits=limits
    )


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

@router.put('/{tariff_id}/update-status')
async def update_tariff_status(tariff_id: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()
    new_status = data.get('status', False)

    tariff = await get_tariff_by_id(
        db_session,
        tariff_id
    )

    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='TARIFF_NOT_FOUND',
            message='Tariff not found'
        )
    
    if tariff.is_active == new_status:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_STATUS_NOT_CHANGED',
            message='Tariff status not changed'
        )
    
    tariff = await update_tariff(
        session=db_session, 
        tariff=tariff, 
        tariff_data={
            'is_active': new_status
        }
    )

    if not tariff:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_STATUS_NOT_CHANGED',
            message='Tariff status not changed'
        )
    
    return response_success(
        tariff=tariff
    )

@router.put('/{tariff_id}/edit', status_code=status.HTTP_200_OK)
async def edit_tariff(tariff_id: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    input_data = await request.json()
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    tariff = await get_tariff_by_id(db_session, tariff_id)

    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='TARIFF_NOT_FOUND',
            message='Tariff not found'
        )
    
    allowed_fields = {'name', 'description', 'price_rub', 'is_active'}
    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}
    
    tariff = await update_tariff(db_session, tariff, update_data)

    if not tariff:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_NOT_UPDATED',
            message='Tariff not updated'
        )
    
    return response_success(tariff=tariff)

@router.delete('/{tariff_id}')
async def delete_tariff(tariff_id: str, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    result = await delete_tariff_by_id(db_session, tariff_id)

    if result == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_NOT_DELETED',
            message='Tariff not deleted'
        )
    
    return response_success(deleting=result)

@router.post('/{tariff_id}/limits/create', status_code=status.HTTP_201_CREATED)
async def create_tariff_limit(tariff_id: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    insert_data = await request.json()

    if not insert_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_LIMITS_DATA_NONE',
            message='Tariff limits data is required'
        )
    
    new_limit = await upsert_limit(
        session=db_session, 
        tariff_id=tariff_id, 
        limit={
            "limit_type": insert_data.get('limit_type', None),
            "limit_value": int(insert_data.get('limit_value', 0))
        }
    )

    if not new_limit:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_LIMITS_NOT_CREATED',
            message='Tariff limits not created'
        )
    
    return response_success(
        limit=new_limit
    )

@router.put('/{tariff_id}/limits/{limit_type}/edit')
async def edit_tariff_limit(tariff_id: str, limit_type: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    if not limit_type:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_TYPE_NONE',
            message='Limit ID is required'
        )
    
    input_data = await request.json()
    if not input_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_LIMITS_DATA_NONE',
            message='Tariff limits data is required'
        )
    
    allowed_fields = {'limit_type', 'limit_value'}
    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}
    
    if not update_data.get('limit_value', None) or not update_data.get('limit_type', None):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_LIMITS_DATA_NONE',
            message='Tariff limits data is required'
        )
    
    limit = await get_limit(
        session=db_session,
        tariff_id=tariff_id,
        limit_type=limit_type
    )

    if not limit:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='LIMIT_NOT_FOUND',
            message='Limit not found'
        )
    
    if str(limit.tariff_id) != tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_NOT_FOUND',
            message='Limit not found'
        )
    
    limit = await update_limit(
        session=db_session,
        limit=limit,
        limit_data=update_data
    )

    if not limit:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_NOT_UPDATED',
            message='Limit not updated'
        )
    
    return response_success(
        limit=limit
    )

@router.delete('/{tariff_id}/limits/{limit_type}/delete')
async def delete_tariff_limit(tariff_id: str, limit_type: str, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    if not limit_type:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_TYPE_NONE',
            message='Limit ID is required'
        )
    
    limit = await get_limit(
        session=db_session,
        tariff_id=tariff_id,
        limit_type=limit_type
    )
    if not limit:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='LIMIT_NOT_FOUND',
            message='Limit not found'
        )
    
    if await delete_limit(db_session, limit) == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_NOT_DELETED',
            message='Limit not deleted'
        )
    
    return response_success(
        deleting=True
    )