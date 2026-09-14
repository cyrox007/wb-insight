from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Database
from core.logger import setup_logger
from core.middleware import auth_middle
from models.users_model import User, UserRole, UserRoleAssociation


logger = setup_logger(__name__)

_ADMIN_ROLES = {UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}


def _conflict(error_type: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"status": "error", "error_type": error_type},
    )


async def _get_roles_for_user(db_session: AsyncSession, user_id: UUID) -> set[str]:
    result = await db_session.execute(
        select(UserRoleAssociation.role).where(UserRoleAssociation.user_id == user_id)
    )
    return {str(role) for role in result.scalars().all() if role}


async def _count_super_admins(db_session: AsyncSession) -> int:
    result = await db_session.execute(
        select(func.count(UserRoleAssociation.id)).where(
            UserRoleAssociation.role == UserRole.SUPER_ADMIN.value
        )
    )
    return int(result.scalar_one())


async def _guard_role_mutation(
    request: Request,
    db_session: AsyncSession,
    actor_user_id: UUID,
) -> None:
    if request.method.upper() != "DELETE":
        return

    parts = request.url.path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["control-panel", "roles"]:
        return

    target_user_raw, role_code = parts[2], parts[3]
    if role_code != UserRole.SUPER_ADMIN.value:
        return

    try:
        target_user_id = UUID(target_user_raw)
    except ValueError:
        return

    if target_user_id == actor_user_id:
        raise _conflict("self_super_admin_removal")

    if await _count_super_admins(db_session) <= 1:
        raise _conflict("last_super_admin")


async def _guard_user_mutation(
    request: Request,
    db_session: AsyncSession,
    actor_user_id: UUID,
    actor_roles: set[str],
) -> None:
    method = request.method.upper()
    if method not in {"DELETE", "PUT", "PATCH"}:
        return

    parts = request.url.path.strip("/").split("/")
    if len(parts) != 3 or parts[:2] != ["control-panel", "users"]:
        return

    try:
        target_user_id = UUID(parts[2])
    except ValueError:
        return

    removes_access = method == "DELETE"
    if method in {"PUT", "PATCH"}:
        try:
            body = await request.json()
        except Exception:
            body = {}
        removes_access = body.get("is_active") is False

    if not removes_access:
        return

    if target_user_id == actor_user_id:
        raise _conflict("self_account_deactivation")

    target_roles = await _get_roles_for_user(db_session, target_user_id)
    if UserRole.SUPER_ADMIN.value not in target_roles:
        return

    if UserRole.SUPER_ADMIN.value not in actor_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "super_admin_required"},
        )

    if await _count_super_admins(db_session) <= 1:
        raise _conflict("last_super_admin")


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
        await _guard_role_mutation(request, db_session, user_id)
        return

    if not roles.intersection(_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "error_type": "admin_required"},
        )

    await _guard_user_mutation(request, db_session, user_id, roles)


async def get_db_session(request: Request) -> AsyncSession:  # type: ignore
    """FastAPI dependency for a transactional async database session."""
    db_session = await Database.get_session()
    try:
        await _authorize_control_panel(request, db_session)
        yield db_session  # type: ignore
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()
