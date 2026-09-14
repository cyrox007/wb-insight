"""Модуль управления пользователями в панели администратора."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from services.user_service import (
    delete_user,
    get_user_by_uuid,
    get_user_list,
    update_user,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix='/control-panel/users', tags=['Control Panel'])


def _user_to_dict(user) -> dict:
    insp = inspect(user)
    user_dict = {
        key: getattr(user, key)
        for key in insp.mapper.column_attrs.keys()
    }
    user_dict.pop('hashed_password', None)
    user_dict['id'] = str(user.id)
    user_dict['roles'] = [
        {
            'role': role.role,
            'assigned_at': role.assigned_at,
            'assigned_by': str(role.assigned_by) if role.assigned_by else None,
        }
        for role in user.roles
    ]
    return user_dict


@router.get('/')
async def get_users(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_list = await get_user_list(db_session)
    return response_success(user_list=[_user_to_dict(user) for user in user_list])


@router.get('/{user_uuid}')
async def get_user(
    user_uuid: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    return response_success(target_user=_user_to_dict(target_user))


@router.put('/{user_uuid}')
async def edit_user(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    allowed_fields = {
        'full_name',
        'entity_type',
        'inn',
        'kpp',
        'legal_address',
        'timezone',
        'is_active',
        'is_staff',
        'staff_id',
        'department',
        'position',
    }

    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    input_data = await request.json()
    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}
    if not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='No valid fields to update',
            code="NO_VALID_FIELDS",
        )

    new_user = await update_user(
        session=db_session,
        user=target_user,
        user_data=update_data,
    )
    if not new_user:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='Failed to update user',
            code="UPDATE_FAILED",
        )

    return response_success(user=_user_to_dict(new_user))


@router.delete('/{user_uuid}')
async def remove_user(
    user_uuid: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    if not await delete_user(db_session, target_user):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='Failed to delete user',
            code="DELETE_FAILED",
        )

    return response_success(deleted=True)
