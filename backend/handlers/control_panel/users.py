"""Модуль управления пользователями в панели администратора."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission, permissions_for_roles
from core.authorization import require_permission
from core.dependencies import get_db_session
from models.users_model import EntityType, UserRole
from services.account_lifecycle_service import (
    deactivate_account,
    list_lifecycle_events,
    reactivate_account,
    record_lifecycle_event,
    revoke_user_sessions,
)
from services.email_verification_service import admin_change_email_identity, admin_verify_email
from services.user_service import (
    get_user_by_email,
    get_user_by_phone,
    get_user_by_uuid,
    get_user_list,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix='/control-panel/users',
    tags=['Control Panel'],
    dependencies=[Depends(require_permission(Permission.USERS_READ))],
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
    user_dict['permissions'] = sorted(
        permission.value
        for permission in permissions_for_roles(role.role for role in user.roles)
    )
    return user_dict


def _can_manage_sensitive_target(request: Request, target_user) -> bool:
    """Only a super-admin may perform access mutations on another super-admin."""
    target_roles = {str(role.role) for role in target_user.roles if role.role}
    if UserRole.SUPER_ADMIN.value not in target_roles:
        return True
    actor_roles = {str(role) for role in getattr(request.state, 'roles', set())}
    return UserRole.SUPER_ADMIN.value in actor_roles


def _reject_sensitive_target(response: Response) -> dict:
    response.status_code = status.HTTP_403_FORBIDDEN
    return response_error(
        code='SUPER_ADMIN_REQUIRED',
        message='Действие над аккаунтом super_admin доступно только super_admin',
    )


@router.get('/')
async def get_users(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_list = await get_user_list(db_session, limit=None)
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


@router.put('/{user_uuid}', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
async def edit_user(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    allowed_fields = {
        'full_name',
        'email',
        'phone',
        'entity_type',
        'inn',
        'kpp',
        'legal_address',
        'tax_rate',
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
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

    input_data = await request.json()
    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}
    if not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='No valid fields to update',
            code="NO_VALID_FIELDS",
        )

    full_name = str(update_data.get('full_name', target_user.full_name) or '').strip()
    if not full_name or len(full_name) > 255:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code='VALIDATION_ERROR', message='Укажите корректное имя или название')
    update_data['full_name'] = full_name

    entity_type = str(update_data.get('entity_type', target_user.entity_type) or '').strip()
    if entity_type not in {item.value for item in EntityType}:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code='VALIDATION_ERROR', message='Неизвестный тип аккаунта')
    update_data['entity_type'] = entity_type

    if 'email' in update_data:
        email = str(update_data.get('email') or '').strip().lower()
        if not email or '@' not in email or len(email) > 254:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code='VALIDATION_ERROR', message='Укажите корректный email')
        owner = await get_user_by_email(db_session, email)
        if owner is not None and owner.id != target_user.id:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(code='EMAIL_ALREADY_EXISTS', message='Этот email уже используется')
        update_data['email'] = email

    if 'phone' in update_data:
        phone = str(update_data.get('phone') or '').strip()
        if not phone or len(phone) > 20:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code='VALIDATION_ERROR', message='Укажите корректный телефон')
        owner = await get_user_by_phone(db_session, phone)
        if owner is not None and owner.id != target_user.id:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(code='PHONE_ALREADY_EXISTS', message='Этот телефон уже используется')
        update_data['phone'] = phone

    if 'tax_rate' in update_data:
        try:
            tax_rate = float(update_data.get('tax_rate'))
        except (TypeError, ValueError):
            tax_rate = -1
        if tax_rate < 0 or tax_rate > 1:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code='VALIDATION_ERROR', message='Налоговая ставка должна быть от 0 до 100%')
        update_data['tax_rate'] = tax_rate

    for field, limit in {
        'timezone': 50,
        'staff_id': 50,
        'department': 100,
        'position': 100,
    }.items():
        if field in update_data:
            value = str(update_data.get(field) or '').strip()
            if len(value) > limit:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return response_error(code='VALIDATION_ERROR', message=f'Поле {field} слишком длинное')
            update_data[field] = value or None

    for field, limit in {'inn': 12, 'kpp': 9}.items():
        if field in update_data:
            value = str(update_data.get(field) or '').strip()
            if len(value) > limit:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return response_error(code='VALIDATION_ERROR', message=f'Поле {field} слишком длинное')
            update_data[field] = value or None

    if 'legal_address' in update_data:
        update_data['legal_address'] = str(update_data.get('legal_address') or '').strip() or None

    actor_user_id = UUID(str(request.state.user_id))
    email_changed = (
        'email' in update_data
        and update_data['email'] != str(target_user.email or '').strip().lower()
    )
    phone_changed = (
        'phone' in update_data
        and update_data['phone'] != str(target_user.phone or '').strip()
    )

    if email_changed:
        await admin_change_email_identity(
            db_session,
            target_user,
            new_email=update_data.pop('email'),
            actor_user_id=actor_user_id,
        )
    else:
        update_data.pop('email', None)

    for key, value in update_data.items():
        setattr(target_user, key, value)

    if phone_changed:
        target_user.session_version += 1
        await record_lifecycle_event(
            db_session,
            user_id=target_user.id,
            actor_user_id=actor_user_id,
            event_type='phone_changed_by_admin',
            event_data={'source': 'control_panel'},
        )

    await record_lifecycle_event(
        db_session,
        user_id=target_user.id,
        actor_user_id=actor_user_id,
        event_type='profile_updated_by_admin',
        event_data={'fields': sorted(update_data.keys() | ({'email'} if email_changed else set()))},
    )
    await db_session.flush()
    await db_session.refresh(target_user)
    return response_success(user=_user_to_dict(target_user))


@router.post('/{user_uuid}/verify-email', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
async def verify_user_email(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='User not found', code='USER_NOT_FOUND')
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

    body = await request.json()
    changed = await admin_verify_email(
        db_session,
        target_user,
        actor_user_id=UUID(str(request.state.user_id)),
        reason=str(body.get('reason') or '').strip() or None,
    )
    if not changed:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code='EMAIL_ALREADY_VERIFIED', message='Email уже подтверждён')
    return response_success(
        verified=True,
        email=target_user.email,
        email_verified_at=target_user.email_verified_at,
    )


@router.delete('/{user_uuid}', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
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
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

    actor_user_id = UUID(str(request.state.user_id))
    if actor_user_id == target_user.id:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SELF_DEACTIVATION_USE_ACCOUNT_FLOW",
            message="Для деактивации собственного аккаунта используйте раздел безопасности аккаунта",
        )

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


@router.post('/{user_uuid}/reactivate', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
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
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

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


@router.post('/{user_uuid}/revoke-sessions', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
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
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

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


@router.post('/{user_uuid}/lifecycle-events', dependencies=[Depends(require_permission(Permission.USERS_WRITE))])
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
