from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission, permissions_for_role
from core.authorization import require_permission
from core.dependencies import get_db_session
from models.users_model import UserRole
from services.user_service import (
    create_user_role_association,
    delete_role_association,
    get_role_associations_for_update,
    get_user_by_uuid,
    get_user_role_association_by_code,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix="/control-panel/roles",
    tags=["Роли"],
    dependencies=[Depends(require_permission(Permission.ROLES_READ))],
)

ROLE_CODES = frozenset(role.value for role in UserRole)


def _parse_user_id(raw_value) -> UUID | None:
    try:
        return UUID(str(raw_value))
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_role_code(raw_value) -> str:
    return str(raw_value or "").strip().lower()


@router.get("/")
async def get_roles(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    roles_list = [
        {
            "code": role.value,
            "permissions": sorted(
                permission.value for permission in permissions_for_role(role)
            ),
        }
        for role in UserRole
    ]
    return response_success(
        roles=roles_list,
        permissions=[permission.value for permission in Permission],
        can_manage=(
            Permission.ROLES_WRITE.value
            in set(getattr(request.state, "permissions", set()))
        ),
    )


@router.post(
    "/",
    dependencies=[Depends(require_permission(Permission.ROLES_WRITE))],
)
async def create_role(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        input_data = await request.json()
    except ValueError:
        input_data = None

    if not isinstance(input_data, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message="Ожидается JSON-объект с пользователем и ролью",
            code="ROLE_PAYLOAD_INVALID",
        )

    user_id = _parse_user_id(input_data.get("user_id"))
    role_code = _normalize_role_code(input_data.get("role"))

    if user_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message="Некорректный идентификатор пользователя",
            code="USER_ID_INVALID",
        )

    if role_code not in ROLE_CODES:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message="Неизвестная системная роль",
            code="ROLE_INVALID",
        )

    target_user = await get_user_by_uuid(db_session, user_id)
    if target_user is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message="Пользователь не найден",
            code="USER_NOT_FOUND",
        )

    existing = await get_user_role_association_by_code(
        session=db_session,
        user_id=str(user_id),
        role_code=role_code,
    )
    if existing is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            message="Эта роль уже назначена пользователю",
            code="ROLE_ALREADY_ASSIGNED",
        )

    actor_user_id = _parse_user_id(getattr(request.state, "user_id", None))
    if actor_user_id is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            message="Не удалось определить текущего администратора",
            code="ACTOR_ID_INVALID",
        )

    await create_user_role_association(
        session=db_session,
        user_id=str(user_id),
        role_code=role_code,
        assigned_by=str(actor_user_id),
    )

    return response_success(
        message="Роль успешно добавлена",
        code="ROLE_CREATED",
    )


@router.delete(
    "/{user_id}/{role_code}",
    dependencies=[Depends(require_permission(Permission.ROLES_WRITE))],
)
async def remove_role(
    user_id: str,
    role_code: str,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    parsed_user_id = _parse_user_id(user_id)
    normalized_role = _normalize_role_code(role_code)

    if parsed_user_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message="Некорректный идентификатор пользователя",
            code="USER_ID_INVALID",
        )

    if normalized_role not in ROLE_CODES:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            message="Неизвестная системная роль",
            code="ROLE_INVALID",
        )

    if normalized_role == UserRole.USER.value:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            message="Базовую роль пользователя удалить нельзя",
            code="BASE_ROLE_PROTECTED",
        )

    target_role = await get_user_role_association_by_code(
        session=db_session,
        user_id=str(parsed_user_id),
        role_code=normalized_role,
    )
    if target_role is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            message="У пользователя нет указанной роли",
            code="ROLE_NOT_FOUND",
        )

    if normalized_role == UserRole.SUPER_ADMIN.value:
        actor_user_id = _parse_user_id(getattr(request.state, "user_id", None))
        if actor_user_id is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return response_error(
                message="Не удалось определить текущего администратора",
                code="ACTOR_ID_INVALID",
            )

        if actor_user_id == parsed_user_id:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                message="Нельзя снять роль super_admin с собственного аккаунта",
                code="SELF_SUPER_ADMIN_REMOVAL_FORBIDDEN",
            )

        locked_super_admin_roles = await get_role_associations_for_update(
            db_session,
            UserRole.SUPER_ADMIN.value,
        )
        if len(locked_super_admin_roles) <= 1:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                message="В системе должен остаться хотя бы один super_admin",
                code="LAST_SUPER_ADMIN_REQUIRED",
            )

    await delete_role_association(
        session=db_session,
        target_role=target_role,
    )

    return response_success(
        message="Роль успешно удалена",
        code="ROLE_DELETED",
    )
