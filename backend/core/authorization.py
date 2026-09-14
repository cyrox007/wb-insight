from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def require_admin(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require an authenticated administrator or super administrator."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)

    if not roles.intersection(ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "admin_required"},
        )


async def require_super_admin(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """Require a super administrator for security-sensitive role changes."""
    await auth_middle(request)
    roles = await _get_active_user_roles(request, db_session)

    if UserRole.SUPER_ADMIN.value not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "super_admin_required"},
        )
