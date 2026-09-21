from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission, permissions_for_roles
from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.users_model import User, UserRole, UserRoleAssociation


ADMIN_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
}


async def _get_active_user_roles(
    request: Request,
    db_session: AsyncSession,
) -> set[str]:
    """Load roles from the database for the authenticated active user.

    Roles are deliberately not trusted from the JWT or frontend state. This
    makes role changes effective immediately and prevents stale/forged client
    state from granting control-panel access.
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
    """Create a FastAPI dependency enforcing one application permission.

    Roles are loaded from the database on every protected request so permission
    changes take effect immediately. The resolved permission set is exposed on
    request.state for handlers/UI capability payloads, but authorization never
    trusts frontend state or JWT role claims.
    """
    async def dependency(
        request: Request,
        db_session: AsyncSession = Depends(get_db_session),
    ) -> None:
        await auth_middle(request)
        roles = await _get_active_user_roles(request, db_session)
        permissions = permissions_for_roles(roles)
        request.state.permissions = {item.value for item in permissions}

        if permission not in permissions:
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
    """Compatibility dependency for control-panel access."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)
    permissions = permissions_for_roles(roles)
    request.state.permissions = {item.value for item in permissions}

    if Permission.CONTROL_PANEL_ACCESS not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "admin_required"},
        )


async def require_super_admin(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """Compatibility dependency for super-admin-only operations."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)
    permissions = permissions_for_roles(roles)
    request.state.permissions = {item.value for item in permissions}

    if Permission.SYSTEM_MANAGE not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "super_admin_required"},
        )
