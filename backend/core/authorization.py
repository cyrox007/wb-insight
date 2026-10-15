from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission, permissions_for_roles
from core.dependencies import get_db_session
from core.middleware import auth_middle
from core.operation_context import get_operation_context
from models.users_model import User, UserRole, UserRoleAssociation
from services.operation_log_service import persist_current_operation_event


ADMIN_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
}


async def _trace_authorization(
    *,
    request: Request,
    required_permission: str,
    roles: set[str],
    permissions: set[Permission],
    allowed: bool,
) -> None:
    if get_operation_context() is None:
        return
    user_id = getattr(request.state, "user_id", None)
    await persist_current_operation_event(
        domain="auth",
        operation="permission_check",
        step="permission_allowed" if allowed else "permission_denied",
        status="success" if allowed else "warning",
        severity="info" if allowed else "warning",
        event_kind="security_decision",
        component="authorization",
        direction="internal",
        user_id=user_id,
        subject_type="user" if user_id else None,
        subject_id=user_id,
        error_code=None if allowed else "permission_denied",
        message=(
            f"Доступ разрешён по праву {required_permission}"
            if allowed
            else f"Доступ отклонён: отсутствует право {required_permission}"
        ),
        input_data={
            "required_permission": required_permission,
            "path": request.url.path,
            "method": request.method,
        },
        output_data={
            "roles": sorted(roles),
            "effective_permissions": sorted(item.value for item in permissions),
            "allowed": allowed,
        },
    )


async def _get_active_user_roles(
    request: Request,
    db_session: AsyncSession,
) -> set[str]:
    """Загружает роли из БД для активного аутентифицированного пользователя.

    Роли намеренно не доверяются JWT и состоянию фронтенда. Поэтому изменение
    ролей начинает действовать сразу, а устаревшее клиентское состояние не может
    выдать дополнительный доступ к панели управления.
    """
    payload = getattr(request.state, "user", None) or {}
    raw_user_id = payload.get("sub")

    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token"},
        )

    try:
        user_id = UUID(str(raw_user_id))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token"},
        )

    result = await db_session.execute(
        select(User.is_active, UserRoleAssociation.role)
        .outerjoin(
            UserRoleAssociation,
            UserRoleAssociation.user_id == User.id,
        )
        .where(User.id == user_id)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "user_not_found"},
        )

    if not any(bool(row.is_active) for row in rows):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "user_inactive"},
        )

    roles = {str(row.role) for row in rows if row.role}
    request.state.roles = roles
    request.state.user_id = user_id
    return roles


def require_permission(permission: Permission):
    """Создаёт зависимость FastAPI для проверки одного прикладного права."""
    async def dependency(
        request: Request,
        db_session: AsyncSession = Depends(get_db_session),
    ) -> None:
        await auth_middle(request)
        roles = await _get_active_user_roles(request, db_session)
        permissions = permissions_for_roles(roles)
        request.state.permissions = {item.value for item in permissions}
        allowed = permission in permissions
        await _trace_authorization(
            request=request,
            required_permission=permission.value,
            roles=roles,
            permissions=permissions,
            allowed=allowed,
        )

        if not allowed:
            request.state.audit_error_code = "permission_denied"
            request.state.audit_metadata = {
                "required_permission": permission.value,
            }
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "error_type": "permission_denied",
                    "required_permission": permission.value,
                },
            )

    dependency.required_permission = permission.value
    return dependency


async def require_admin(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """Совместимая проверка доступа к панели управления."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)
    permissions = permissions_for_roles(roles)
    request.state.permissions = {item.value for item in permissions}
    allowed = Permission.CONTROL_PANEL_ACCESS in permissions
    await _trace_authorization(
        request=request,
        required_permission=Permission.CONTROL_PANEL_ACCESS.value,
        roles=roles,
        permissions=permissions,
        allowed=allowed,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "admin_required"},
        )


async def require_super_admin(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """Совместимая проверка операций, доступных только системному администратору."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)
    permissions = permissions_for_roles(roles)
    request.state.permissions = {item.value for item in permissions}
    allowed = Permission.SYSTEM_MANAGE in permissions
    await _trace_authorization(
        request=request,
        required_permission=Permission.SYSTEM_MANAGE.value,
        roles=roles,
        permissions=permissions,
        allowed=allowed,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "super_admin_required"},
        )