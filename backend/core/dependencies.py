from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Database
from core.logger import setup_logger
from core.middleware import auth_middle
from models.users_model import User, UserRole, UserRoleAssociation


logger = setup_logger(__name__)

_ADMIN_ROLES = {UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}


async def _authorize_control_panel(request: Request, db_session: AsyncSession) -> None:
    """Protect every current control-panel endpoint at the shared DB boundary."""
    if not request.url.path.startswith('/control-panel'):
        return

    await auth_middle(request)

    payload = request.state.user
    try:
        user_id = UUID(str(payload.get('sub')))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token"},
        )

    result = await db_session.execute(
        select(User.is_active, UserRoleAssociation.role)
        .outerjoin(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
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

    role_mutation = (
        request.url.path.startswith('/control-panel/roles')
        and request.method.upper() in {'POST', 'PUT', 'PATCH', 'DELETE'}
    )

    if role_mutation:
        if UserRole.SUPER_ADMIN.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "error_type": "super_admin_required"},
            )
        return

    if not roles.intersection(_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "admin_required"},
        )


async def get_db_session(request: Request) -> AsyncSession:  # type: ignore
    """FastAPI dependency for a transactional async database session."""
    db_session = await Database.get_session()
    try:
        await _authorize_control_panel(request, db_session)
        yield db_session  # type: ignore
        await db_session.commit()
    finally:
        await db_session.close()
