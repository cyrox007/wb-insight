from decimal import Decimal
from typing import cast
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from core.logger import setup_logger
from models.tariffs_model import TariffLimit
from services.tariff_service import (
    get_tariffs_list, 
    insert_tariff, 
    get_tariff_by_id, 
    update_tariff, 
    get_tariff_limits_by_id, 
    delete_tariff_by_id,
    upsert_limit,
    get_limit,
    update_limit,
    delete_limit,
    REQUIRED_ACTIVE_LIMITS,
    get_missing_required_limits,
    is_system_tariff,
    normalized_tariff_code,
    validate_limit_value,
)
from utils.responce_helps import response_error, response_success

router = APIRouter(
    prefix='/control-panel/tariffs',
    tags=['Tariffs'],
    dependencies=[Depends(require_permission(Permission.TARIFFS_READ))],
)

logger = setup_logger(__name__)

@router.get('/')
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session)

    return response_success(tariffs=tariffs)

@router.get('/{tariff_id}')
async def get_tariff(tariff_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
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

    limits = await get_tariff_limits_by_id(db_session, cast(UUID, tariff.id))
    
    return response_success(
        tariff=tariff,
        limits=limits
    )


@router.post('/create', status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
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
    
    normalized_code = normalized_tariff_code(code.replace(' ', '_'))
    if normalized_code == 'demo':
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='SYSTEM_TARIFF_RESERVED',
            message='Тариф demo является системным и создаётся автоматически'
        )

    if is_active:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='TARIFF_LIMITS_REQUIRED',
            message='Сначала создайте тариф неактивным, настройте обязательные лимиты, затем активируйте его'
        )

    code = normalized_code.upper()

    cleaned = str(price_raw).strip().replace(',', '.')
    price_rub = Decimal(cleaned).quantize(Decimal('0.00'))

    tariff = await insert_tariff(db_session, {
        'code': code,
        'name': name,
        'description': description,
        'price_rub': price_rub,
        'is_active': is_active,
        'is_public': False
    })

    if not tariff:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_EXISTS',
            message='Tariff with this code already exists'
        )
    
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        return response_error(
            code='TARIFF_NOT_CREATED', message=str(e)
        )

    return response_success(tariff=tariff)

@router.put('/{tariff_id}/update-status', dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def update_tariff_status(tariff_id: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()
    new_status = data.get('status', False)

    tariff = await get_tariff_by_id(
        db_session,
        UUID(tariff_id)
    )

    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='TARIFF_NOT_FOUND',
            message='Tariff not found'
        )
    
    if is_system_tariff(tariff) and not new_status:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='SYSTEM_TARIFF_PROTECTED',
            message='Системный тариф demo нельзя деактивировать'
        )

    if new_status:
        missing_limits = await get_missing_required_limits(db_session, tariff.id)
        if missing_limits:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code='TARIFF_LIMITS_INCOMPLETE',
                message='Нельзя активировать тариф без обязательных runtime-лимитов',
                missing_limits=missing_limits
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
            'is_active': new_status,
            **({'is_public': False} if not new_status else {})
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

@router.put('/{tariff_id}/edit', status_code=status.HTTP_200_OK, dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def edit_tariff(tariff_id: UUID, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
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
    
    allowed_fields = {'name', 'description', 'price_rub', 'is_active', 'is_public'}
    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}

    if is_system_tariff(tariff):
        requested_price = Decimal(str(update_data.get('price_rub', tariff.price_rub)))
        requested_active = bool(update_data.get('is_active', tariff.is_active))
        requested_public = bool(update_data.get('is_public', tariff.is_public))
        if requested_price != Decimal('0.00') or not requested_active or requested_public:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code='SYSTEM_TARIFF_PROTECTED',
                message='Для demo обязательны цена 0 ₽, активный статус и скрытие из публичного каталога'
            )

    target_active = bool(update_data.get('is_active', tariff.is_active))
    target_public = bool(update_data.get('is_public', tariff.is_public))
    if target_public and not target_active:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='TARIFF_PUBLIC_REQUIRES_ACTIVE',
            message='Публичный тариф должен быть активным'
        )

    if target_active:
        missing_limits = await get_missing_required_limits(db_session, tariff.id)
        if missing_limits:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code='TARIFF_LIMITS_INCOMPLETE',
                message='Активный тариф должен содержать обязательные runtime-лимиты',
                missing_limits=missing_limits
            )

    tariff = await update_tariff(db_session, tariff, update_data)

    if not tariff:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_NOT_UPDATED',
            message='Tariff not updated'
        )
    
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        return response_error(
            code='TARIFF_NOT_UPDATED', message=str(e)
        )
    
    return response_success(tariff=tariff)

@router.delete('/{tariff_id}', dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def delete_tariff(tariff_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    if not tariff_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_ID_NONE',
            message='Tariff ID is required'
        )
    
    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code='TARIFF_NOT_FOUND', message='Tariff not found')

    if is_system_tariff(tariff):
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='SYSTEM_TARIFF_PROTECTED',
            message='Системный тариф demo нельзя удалить'
        )

    result = await delete_tariff_by_id(db_session, tariff_id)

    if result == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_NOT_DELETED',
            message='Tariff not deleted'
        )
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response_error(
            code='TARIFF_NOT_DELETED', message=str(e)
        )
    return response_success(deleting=result)

@router.post('/{tariff_id}/limits/create', status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def create_tariff_limit(tariff_id: UUID, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
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
    
    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code='TARIFF_NOT_FOUND', message='Tariff not found')

    limit_type_value = str(insert_data.get('limit_type') or '').strip()
    try:
        limit_value = int(insert_data.get('limit_value', 0))
        validate_limit_value(limit_type_value, limit_value)
    except (TypeError, ValueError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code='LIMIT_VALUE_INVALID', message=str(exc))

    new_limit = await upsert_limit(
        session=db_session, 
        tariff_id=tariff_id, 
        limit={
            "limit_type": limit_type_value,
            "limit_value": limit_value
        }
    )

    if not new_limit:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='TARIFF_LIMITS_NOT_CREATED',
            message='Tariff limits not created'
        )
    
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        return response_error(
            code='TARIFF_LIMITS_NOT_CREATED', message=str(e)
        )
    
    return response_success(
        limit=new_limit
    )

@router.put('/{tariff_id}/limits/{limit_type}/edit', dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def edit_tariff_limit(tariff_id: UUID, limit_type: str, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    logger.info(f"tariff_id={tariff_id}, limit_type='{limit_type}'")
    logger.info(f"type(tariff_id)={type(tariff_id)}")
    logger.info(f"DB QUERY tariff_id={tariff_id}, limit_type='{limit_type}'")
    query = select(TariffLimit).where(TariffLimit.tariff_id == tariff_id)
    res = await db_session.execute(query)
    logger.info(f"ALL LIMITS: {[l.limit_type for l in res.scalars().all()]}")
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
    
    if 'limit_value' not in input_data:
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
    
    try:
        validate_limit_value(limit_type, int(input_data['limit_value']))
    except (TypeError, ValueError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code='LIMIT_VALUE_INVALID', message=str(exc))

    limit = await update_limit(
        session=db_session,
        limit=limit,
        limit_data=input_data
    )

    if not limit:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_NOT_UPDATED',
            message='Limit not updated'
        )
    
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        return response_error(
            code='LIMIT_NOT_UPDATED', message=str(e)
        )
    
    return response_success(
        limit=limit
    )

@router.delete('/{tariff_id}/limits/{limit_type}/delete', dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))])
async def delete_tariff_limit(tariff_id: UUID, limit_type: str, response: Response, db_session: AsyncSession = Depends(get_db_session)):
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
    
    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code='TARIFF_NOT_FOUND', message='Tariff not found')

    if tariff.is_active and limit_type in REQUIRED_ACTIVE_LIMITS:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='REQUIRED_TARIFF_LIMIT_PROTECTED',
            message='Обязательный runtime-лимит нельзя удалить у активного тарифа; измените его значение'
        )

    if await delete_limit(db_session, limit) == False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='LIMIT_NOT_DELETED',
            message='Limit not deleted'
        )
    
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response_error(
            code='LIMIT_NOT_DELETED', message=str(e)
        )
    
    return response_success(
        deleting=True
    )