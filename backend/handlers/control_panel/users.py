"""Модуль управления пользователями в панели администратора."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from core.authorization import require_admin
from core.dependencies import get_db_session
from services.account_lifecycle_service import (
    deactivate_account,
    list_lifecycle_events,
    reactivate_account,
    record_lifecycle_event,
    revoke_user_sessions,
)
from services.user_service import (
    get_user_by_uuid,
    get_user_list,
    update_user,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix='/control-panel/users',
    tags=['Control Panel'],
    dependencies=[Depends(require_admin)],
)

SUPPORT_EVENT_TYPES = frozenset({
    'support_access_review',
    'support_payment_review',
    'support_refund_requested',
    'support_refund_completed',
})


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
    # Account activation state is intentionally excluded: lifecycle endpoints
    # provide audit evidence and revoke sessions consistently.
    allowed_fields = {
        'full_name',
        'entity_type',
        'inn',
        'kpp',
        'legal_address',
        'timezone',
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
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Soft-deactivate an account; destructive purge is never an admin default."""
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    actor_user_id = UUID(str(request.state.user_id))
    changed = await deactivate_account(
        db_session,
        target_user,
        actor_user_id=actor_user_id,
        reason="admin_deactivation",
    )
    if not changed:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            message='Account is already inactive',
            code="ACCOUNT_ALREADY_INACTIVE",
        )

    return response_success(
        deactivated=True,
        retention_until=(
            target_user.retention_until.isoformat()
            if target_user.retention_until
            else None
        ),
    )


@router.post('/{user_uuid}/reactivate')
async def reactivate_user(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    body = await request.json()
    changed = await reactivate_account(
        db_session,
        target_user,
        actor_user_id=UUID(str(request.state.user_id)),
        reason=str(body.get('reason') or '').strip() or None,
    )
    if not changed:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="ACCOUNT_ALREADY_ACTIVE", message="Аккаунт уже активен")
    return response_success(reactivated=True)


@router.post('/{user_uuid}/revoke-sessions')
async def revoke_sessions(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")
    body = await request.json()
    await revoke_user_sessions(
        db_session,
        target_user,
        actor_user_id=UUID(str(request.state.user_id)),
        reason=str(body.get('reason') or '').strip() or None,
    )
    return response_success(revoked=True)


@router.get('/{user_uuid}/lifecycle-events')
async def get_lifecycle_events(
    user_uuid: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")
    events = await list_lifecycle_events(db_session, user_id=user_uuid)
    return response_success(
        events=[
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
                "reason": event.reason,
                "reference_id": event.reference_id,
                "event_data": event.event_data,
                "created_at": event.created_at,
            }
            for event in events
        ]
    )


@router.post('/{user_uuid}/lifecycle-events')
async def add_support_lifecycle_event(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Record a bounded support action without direct production DB edits.

    This endpoint deliberately does not perform a provider refund or alter a
    payment. It creates durable evidence around a support/provider action whose
    actual monetary execution remains subject to the approved payment policy.
    """
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code="USER_NOT_FOUND")

    body = await request.json()
    event_type = str(body.get('event_type') or '').strip()
    reason = str(body.get('reason') or '').strip()
    reference_id = str(body.get('reference_id') or '').strip() or None

    if event_type not in SUPPORT_EVENT_TYPES:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='INVALID_SUPPORT_EVENT_TYPE',
            message='Недопустимый тип support-события',
        )
    if not reason or len(reason) > 1000:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='VALIDATION_ERROR',
            message='Причина обязательна и должна быть не длиннее 1000 символов',
        )
    if reference_id is not None and len(reference_id) > 128:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='VALIDATION_ERROR',
            message='reference_id должен быть не длиннее 128 символов',
        )

    event = await record_lifecycle_event(
        db_session,
        user_id=user_uuid,
        actor_user_id=UUID(str(request.state.user_id)),
        event_type=event_type,
        reason=reason,
        reference_id=reference_id,
        event_data={'source': 'control_panel'},
    )
    return response_success(
        event={
            'id': str(event.id),
            'event_type': event.event_type,
            'reference_id': event.reference_id,
            'created_at': event.created_at,
        }
    )
