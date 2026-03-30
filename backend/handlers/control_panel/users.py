"""Модуль управления пользователями в панели администратора."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from services.user_service import (
    get_user_by_uuid,
    get_user_list,
    update_user,
    delete_user,
)
from utils.responce_helps import response_success, response_error


router = APIRouter(prefix='/control-panel/users', tags=['Control Panel'])


def _user_to_dict(user) -> dict:
    """Преобразует объект пользователя в словарь.
    
    Args:
        user: Объект модели User.
        
    Returns:
        Словарь с данными пользователя.
    """
    insp = inspect(user)
    user_dict = {
        key: getattr(user, key)
        for key in insp.mapper.column_attrs.keys()
    }
    user_dict.pop('hashed_password', None)
    user_dict['roles'] = [
        {
            'role': role.role,
            'assigned_at': role.assigned_at,
            'assigned_by': str(role.assigned_by) if role.assigned_by else None
        }
        for role in user.roles
    ]
    return user_dict


@router.get('/')
async def get_users(
    db_session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Получение списка всех пользователей.
    
    Args:
        db_session: Сессия базы данных.
        
    Returns:
        Список пользователей.
    """
    user_list = await get_user_list(db_session)
    result = [_user_to_dict(user) for user in user_list]
    
    return response_success(user_list=result)


@router.get('/{user_uuid}')
async def get_user(
    user_uuid: str,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Получение данных пользователя по UUID.
    
    Args:
        user_uuid: UUID пользователя.
        response: HTTP ответ.
        db_session: Сессия базы данных.
        
    Returns:
        Данные пользователя.
    """
    target_user = await get_user_by_uuid(db_session, user_uuid)
    
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message='User not found',
            code="USER_NOT_FOUND"
        )
    
    user_dict = _user_to_dict(target_user)
    
    return response_success(target_user=user_dict)


@router.put('/{user_uuid}')
async def edit_user(
    user_uuid: str,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Редактирование данных пользователя.
    
    Args:
        user_uuid: UUID пользователя.
        request: HTTP запрос с данными для обновления.
        response: HTTP ответ.
        db_session: Сессия базы данных.
        
    Returns:
        Обновленные данные пользователя.
    """
    ALLOWED_FIELDS = [
        'full_name', 'entity_type', 'inn', 'kpp', 'legal_address',
        'timezone', 'is_active', 'is_staff', 'staff_id', 'department', 'position'
    ]
    
    target_user = await get_user_by_uuid(db_session, user_uuid)
    
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message='User not found',
            code="USER_NOT_FOUND"
        )
    
    input_data = await request.json()
    update_data = {k: v for k, v in input_data.items() if k in ALLOWED_FIELDS}
    
    if not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='No valid fields to update',
            code="NO_VALID_FIELDS"
        )
    
    new_user = await update_user(
        session=db_session,
        user=target_user,
        user_data=update_data
    )
    
    if not new_user:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='Failed to update user',
            code="UPDATE_FAILED"
        )
    
    return response_success(user=new_user)


@router.delete('/{user_uuid}')
async def remove_user(
    user_uuid: str,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Удаление пользователя.
    
    Args:
        user_uuid: UUID пользователя.
        response: HTTP ответ.
        db_session: Сессия базы данных.
        
    Returns:
        Результат удаления.
    """
    target_user = await get_user_by_uuid(db_session, user_uuid)
    
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message='User not found',
            code="USER_NOT_FOUND"
        )
    
    if await delete_user(db_session, target_user) is False:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='Failed to delete user',
            code="DELETE_FAILED"
        )
    
    return response_success(deleted=True)