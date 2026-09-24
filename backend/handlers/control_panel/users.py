"""Модуль управления пользователями в панели администратора."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, inspect, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.access_control import Permission, permissions_for_roles
from core.authorization import require_permission
from core.dependencies import get_db_session
from models.users_model import EntityType, User, UserRole, UserRoleAssociation
from services.account_lifecycle_service import (
    deactivate_account,
    list_lifecycle_events,
    reactivate_account,
    record_lifecycle_event,
    revoke_user_sessions,
)
from services.email_verification_service import admin_change_email_identity, admin_verify_email
from services.user_identity import (
    normalize_email,
    normalize_phone,
    validate_legal_identity,
)
from services.user_service import (
    create_user_role_association,
    delete_user,
    get_user_by_email,
    get_user_by_inn,
    get_user_by_phone,
    get_user_by_uuid,
    insert_user,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix='/control-panel/users',
    tags=['Пользователи'],
    dependencies=[Depends(require_permission(Permission.USERS_READ))],
)

SUPPORT_EVENT_TYPES = frozenset({
    'support_access_review',
    'support_payment_review',
    'support_refund_requested',
    'support_refund_completed',
})

STAFF_CREATION_ROLES = frozenset({
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.SUPPORT.value,
    UserRole.ANALYST.value,
})


class StaffCreationError(ValueError):
    """Ошибка проверки данных создаваемого служебного аккаунта."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _validated_staff_creation_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise StaffCreationError(
            'STAFF_CREATE_PAYLOAD_INVALID',
            'Ожидается JSON-объект с данными сотрудника',
        )

    allowed_fields = {
        'full_name',
        'email',
        'phone',
        'password',
        'role',
        'timezone',
        'staff_id',
        'department',
        'position',
    }
    unsupported = sorted(set(payload) - allowed_fields)
    if unsupported:
        raise StaffCreationError(
            'STAFF_CREATE_FIELDS_UNSUPPORTED',
            'Запрос содержит неподдерживаемые поля',
        )

    full_name = str(payload.get('full_name') or '').strip()
    if not full_name or len(full_name) > 255:
        raise StaffCreationError(
            'FULL_NAME_INVALID',
            'Укажите имя сотрудника длиной до 255 символов',
        )

    email = normalize_email(payload.get('email'))
    if email is None:
        raise StaffCreationError('EMAIL_INVALID', 'Укажите корректный email')

    phone = normalize_phone(payload.get('phone'))
    if phone is None:
        raise StaffCreationError('PHONE_INVALID', 'Укажите корректный номер телефона')

    password = payload.get('password')
    if not isinstance(password, str) or len(password) < 8:
        raise StaffCreationError(
            'PASSWORD_INVALID',
            'Временный пароль должен содержать минимум 8 символов',
        )
    if len(password.encode('utf-8')) > 72:
        raise StaffCreationError(
            'PASSWORD_TOO_LONG',
            'Временный пароль не должен превышать 72 байта в кодировке UTF-8',
        )

    role = str(payload.get('role') or '').strip().lower()
    if role not in STAFF_CREATION_ROLES:
        raise StaffCreationError(
            'STAFF_ROLE_INVALID',
            'Выберите допустимую служебную роль',
        )

    timezone_value = str(payload.get('timezone') or 'Europe/Moscow').strip()
    if not timezone_value or len(timezone_value) > 50:
        raise StaffCreationError(
            'TIMEZONE_INVALID',
            'Укажите корректный часовой пояс',
        )

    normalized = {
        'full_name': full_name,
        'email': email,
        'phone': phone,
        'password': password,
        'role': role,
        'timezone': timezone_value,
    }
    for field, limit in {
        'staff_id': 50,
        'department': 100,
        'position': 100,
    }.items():
        value = str(payload.get(field) or '').strip()
        if len(value) > limit:
            raise StaffCreationError(
                'STAFF_FIELD_INVALID',
                f'Поле {field} слишком длинное',
            )
        normalized[field] = value or None

    return normalized


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
    """Разрешает изменения super_admin только другому super_admin."""
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


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _user_list_conditions(
    *,
    search: str | None,
    active: bool | None,
    verified: bool | None,
    staff: bool | None,
    role: str | None,
):
    conditions = []
    normalized_search = str(search or "").strip()
    if normalized_search:
        pattern = f"%{_escape_like(normalized_search)}%"
        conditions.append(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                User.phone.ilike(pattern, escape="\\"),
                User.staff_id.ilike(pattern, escape="\\"),
            )
        )
    if active is not None:
        conditions.append(User.is_active.is_(active))
    if verified is not None:
        conditions.append(
            User.email_verified_at.is_not(None)
            if verified
            else User.email_verified_at.is_(None)
        )
    if staff is not None:
        conditions.append(User.is_staff.is_(staff))
    if role:
        conditions.append(
            User.roles.any(UserRoleAssociation.role == role)
        )
    return conditions


@router.get('/')
async def get_users(
    response: Response,
    search: str | None = Query(default=None, max_length=100),
    active: bool | None = Query(default=None),
    verified: bool | None = Query(default=None),
    staff: bool | None = Query(default=None),
    role: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    normalized_role = str(role or "").strip().lower() or None
    if normalized_role and normalized_role not in {item.value for item in UserRole}:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="USER_FILTER_INVALID",
            message="Неизвестная роль пользователя",
        )

    conditions = _user_list_conditions(
        search=search,
        active=active,
        verified=verified,
        staff=staff,
        role=normalized_role,
    )
    query = (
        select(User)
        .options(selectinload(User.roles))
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(limit)
    )
    count_query = select(func.count(User.id))
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    result = await db_session.execute(query)
    total = await db_session.scalar(count_query)
    return response_success(
        user_list=[_user_to_dict(user) for user in result.scalars().unique().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.post(
    '/',
    dependencies=[
        Depends(require_permission(Permission.USERS_WRITE)),
        Depends(require_permission(Permission.ROLES_WRITE)),
    ],
)
async def create_staff_user(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Создаёт служебный аккаунт из панели суперадминистратора."""

    try:
        payload = await request.json()
    except (TypeError, ValueError):
        payload = None

    try:
        data = _validated_staff_creation_payload(payload)
    except StaffCreationError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code=exc.code, message=exc.message)

    if await get_user_by_email(db_session, data['email']) is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='EMAIL_ALREADY_EXISTS',
            message='Этот email уже используется',
        )

    if await get_user_by_phone(db_session, data['phone']) is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='PHONE_ALREADY_EXISTS',
            message='Этот телефон уже используется',
        )

    actor_user_id = UUID(str(request.state.user_id))
    try:
        async with db_session.begin_nested():
            user = await insert_user(
                db_session,
                {
                    'full_name': data['full_name'],
                    'email': data['email'],
                    'phone': data['phone'],
                    'password': data['password'],
                    'entity_type': EntityType.INDIVIDUAL.value,
                    'timezone': data['timezone'],
                },
            )
            if user is None:
                raise StaffCreationError(
                    'STAFF_CREATE_FAILED',
                    'Не удалось создать служебный аккаунт',
                )

            user.is_staff = True
            user.staff_id = data['staff_id']
            user.department = data['department']
            user.position = data['position']
            user.email_verified_at = datetime.now(timezone.utc)

            await create_user_role_association(
                db_session,
                str(user.id),
                data['role'],
                assigned_by=str(actor_user_id),
            )
            await record_lifecycle_event(
                db_session,
                user_id=user.id,
                actor_user_id=actor_user_id,
                event_type='staff_account_created_by_admin',
                event_data={
                    'source': 'control_panel',
                    'role': data['role'],
                },
            )
            await db_session.flush()
    except IntegrityError:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='STAFF_ACCOUNT_CONFLICT',
            message='Email, телефон или ID сотрудника уже используются',
        )
    except StaffCreationError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code=exc.code, message=exc.message)

    await db_session.refresh(user, attribute_names=['roles'])
    return response_success(
        message='Служебный аккаунт создан',
        user=_user_to_dict(user),
    )


@router.get('/{user_uuid}')
async def get_user(
    user_uuid: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")

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
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

    try:
        input_data = await request.json()
    except (TypeError, ValueError):
        input_data = None
    if not isinstance(input_data, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='USER_UPDATE_PAYLOAD_INVALID',
            message='Ожидается JSON-объект с изменениями пользователя',
        )

    update_data = {k: v for k, v in input_data.items() if k in allowed_fields}
    if not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message='Нет допустимых полей для изменения',
            code="NO_VALID_FIELDS",
        )
    changed_fields = set(update_data)

    if 'full_name' in update_data:
        full_name = str(update_data.get('full_name') or '').strip()
        if not full_name or len(full_name) > 255:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code='VALIDATION_ERROR',
                message='Укажите корректное имя или название',
            )
        update_data['full_name'] = full_name

    target_entity_type = str(
        update_data.get('entity_type', target_user.entity_type) or ''
    ).strip().lower()
    identity_fields = {'entity_type', 'inn', 'kpp', 'legal_address'}
    if changed_fields & identity_fields:
        try:
            identity = validate_legal_identity(
                entity_type=target_entity_type,
                inn_value=update_data.get('inn', target_user.inn),
                kpp_value=update_data.get('kpp', target_user.kpp),
                legal_address_value=update_data.get(
                    'legal_address',
                    target_user.legal_address,
                ),
            )
        except ValueError as exc:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code='LEGAL_IDENTITY_INVALID',
                message=str(exc),
            )

        update_data.update(identity)
        if identity['inn']:
            owner = await get_user_by_inn(db_session, identity['inn'])
            if owner is not None and owner.id != target_user.id:
                response.status_code = status.HTTP_409_CONFLICT
                return response_error(
                    code='INN_ALREADY_EXISTS',
                    message='Этот ИНН уже используется',
                )

    if 'email' in update_data:
        email = normalize_email(update_data.get('email'))
        if email is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code='EMAIL_INVALID',
                message='Укажите корректный email',
            )
        owner = await get_user_by_email(db_session, email)
        if owner is not None and owner.id != target_user.id:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code='EMAIL_ALREADY_EXISTS',
                message='Этот email уже используется',
            )
        update_data['email'] = email

    if 'phone' in update_data:
        phone = normalize_phone(update_data.get('phone'))
        if phone is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code='PHONE_INVALID',
                message='Укажите корректный номер телефона',
            )
        owner = await get_user_by_phone(db_session, phone)
        if owner is not None and owner.id != target_user.id:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code='PHONE_ALREADY_EXISTS',
                message='Этот телефон уже используется',
            )
        update_data['phone'] = phone

    if 'tax_rate' in update_data:
        try:
            tax_rate = float(update_data.get('tax_rate'))
        except (TypeError, ValueError):
            tax_rate = -1
        if tax_rate < 0 or tax_rate > 1:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code='VALIDATION_ERROR',
                message='Налоговая ставка должна быть от 0 до 100%',
            )
        update_data['tax_rate'] = tax_rate

    if 'is_staff' in update_data and not isinstance(update_data['is_staff'], bool):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='STAFF_FLAG_INVALID',
            message='Поле is_staff должно быть логическим значением',
        )

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
                return response_error(
                    code='VALIDATION_ERROR',
                    message=f'Поле {field} слишком длинное',
                )
            update_data[field] = value or None

    actor_user_id = UUID(str(request.state.user_id))
    email_changed = (
        'email' in update_data
        and update_data['email'] != str(target_user.email or '').strip().lower()
    )
    phone_changed = (
        'phone' in update_data
        and update_data['phone'] != str(target_user.phone or '').strip()
    )

    try:
        async with db_session.begin_nested():
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
                event_data={'fields': sorted(changed_fields)},
            )
            await db_session.flush()
    except IntegrityError:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='USER_IDENTITY_CONFLICT',
            message=(
                'Email, телефон, ИНН или другой уникальный идентификатор '
                'уже используется'
            ),
        )

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
        return response_error(message='Пользователь не найден', code='USER_NOT_FOUND')
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
    """Мягко деактивирует аккаунт без необратимого удаления данных."""
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")
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
            message='Аккаунт уже неактивен',
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


@router.delete(
    '/{user_uuid}/purge',
    dependencies=[Depends(require_permission(Permission.USERS_DELETE))],
)
async def permanently_delete_user(
    user_uuid: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Необратимо удаляет ранее деактивированный аккаунт пользователя."""
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message='Пользователь не найден',
            code='USER_NOT_FOUND',
        )
    if not _can_manage_sensitive_target(request, target_user):
        return _reject_sensitive_target(response)

    actor_user_id = UUID(str(request.state.user_id))
    if actor_user_id == target_user.id:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='SELF_DELETE_FORBIDDEN',
            message='Нельзя необратимо удалить собственный аккаунт из панели управления',
        )
    if target_user.is_active:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code='USER_MUST_BE_INACTIVE',
            message='Перед необратимым удалением сначала деактивируйте аккаунт',
        )

    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='USER_DELETE_CONFIRMATION_REQUIRED',
            message='Для удаления требуется подтверждение email пользователя',
        )

    confirm_email = str(body.get('confirm_email') or '').strip().lower()
    target_email = str(target_user.email or '').strip().lower()
    if not confirm_email or confirm_email != target_email:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='USER_DELETE_CONFIRMATION_MISMATCH',
            message='Подтверждение не совпадает с email удаляемого пользователя',
        )

    reason = str(body.get('reason') or '').strip()
    if len(reason) > 1000:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code='VALIDATION_ERROR',
            message='Причина удаления должна быть не длиннее 1000 символов',
        )

    target_roles = sorted(
        str(role.role)
        for role in target_user.roles
        if role.role
    )
    await record_lifecycle_event(
        db_session,
        user_id=target_user.id,
        actor_user_id=actor_user_id,
        event_type='account_permanently_deleted',
        reason=reason or None,
        event_data={
            'source': 'control_panel',
            'deleted_user_id': str(target_user.id),
            'roles': target_roles,
            'was_staff': bool(target_user.is_staff),
        },
    )
    deleted = await delete_user(db_session, target_user)
    if not deleted:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code='USER_NOT_FOUND',
            message='Пользователь уже удалён',
        )

    return response_success(
        deleted=True,
        user_id=str(user_uuid),
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
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")
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
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")
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
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")
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
    """Фиксирует ограниченное support-действие без прямого редактирования БД.

    Маршрут не выполняет возврат средств и не изменяет платёж. Он сохраняет
    долговечное подтверждение действия поддержки или провайдера, а денежная
    операция остаётся в рамках утверждённого платёжного процесса.
    """
    target_user = await get_user_by_uuid(db_session, user_uuid)
    if not target_user:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(message='Пользователь не найден', code="USER_NOT_FOUND")

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
