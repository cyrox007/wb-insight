from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission, permissions_for_roles
from core.database import Database
from core.logger import setup_logger
from core.middleware import auth_middle
from core.operation_context import get_operation_context
from models.users_model import User, UserRole, UserRoleAssociation
from services.operation_log_service import persist_current_operation_event


logger = setup_logger(__name__)
_MAX_DB_CHANGE_ITEMS = 100


def _conflict(error_type: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"status": "error", "error_type": error_type})


def _forbidden(permission: Permission) -> HTTPException:
    error_type = (
        "super_admin_required"
        if permission in {Permission.ROLES_WRITE, Permission.PAYMENTS_WRITE, Permission.MAIL_WRITE}
        else "admin_required"
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"status": "error", "error_type": error_type, "permission": permission.value},
    )


def _required_control_panel_permission(request: Request) -> Permission:
    path = request.url.path
    is_read = request.method.upper() in {"GET", "HEAD"}
    if path.startswith("/control-panel/users"):
        return Permission.USERS_READ if is_read else Permission.USERS_WRITE
    if path.startswith("/control-panel/roles"):
        return Permission.ROLES_READ if is_read else Permission.ROLES_WRITE
    if path.startswith("/control-panel/tariffs"):
        return Permission.TARIFFS_READ if is_read else Permission.TARIFFS_WRITE
    if path.startswith("/control-panel/payments"):
        return Permission.PAYMENTS_READ if is_read else Permission.PAYMENTS_WRITE
    if path.startswith("/control-panel/audit"):
        return Permission.AUDIT_READ
    if path.startswith("/control-panel/mail"):
        return Permission.MAIL_READ if is_read else Permission.MAIL_WRITE
    return Permission.CONTROL_PANEL_ACCESS


async def _get_roles_for_user(db_session: AsyncSession, user_id: UUID) -> set[str]:
    result = await db_session.execute(select(UserRoleAssociation.role).where(UserRoleAssociation.user_id == user_id))
    return {str(role) for role in result.scalars().all() if role}


async def _count_super_admins(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count(UserRoleAssociation.id)).where(UserRoleAssociation.role == UserRole.SUPER_ADMIN.value))
    return int(result.scalar_one())


async def _guard_role_mutation(request: Request, db_session: AsyncSession, actor_user_id: UUID) -> None:
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
    actor_permissions: frozenset[Permission],
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
    if Permission.ROLES_WRITE not in actor_permissions:
        raise _forbidden(Permission.ROLES_WRITE)
    if await _count_super_admins(db_session) <= 1:
        raise _conflict("last_super_admin")


async def _authorize_control_panel(request: Request, db_session: AsyncSession) -> None:
    if not request.url.path.startswith("/control-panel"):
        return
    await auth_middle(request)
    payload = request.state.user
    try:
        user_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"status": "error", "error_type": "invalid_token"})

    result = await db_session.execute(
        select(User.is_active, UserRoleAssociation.role)
        .outerjoin(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
        .where(User.id == user_id)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"status": "error", "error_type": "user_not_found"})
    if not any(bool(row.is_active) for row in rows):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"status": "error", "error_type": "user_inactive"})

    roles = {str(row.role) for row in rows if row.role}
    permissions = permissions_for_roles(roles)
    required_permission = _required_control_panel_permission(request)
    request.state.roles = roles
    request.state.permissions = {permission.value for permission in permissions}
    request.state.user_id = user_id
    if required_permission not in permissions:
        raise _forbidden(required_permission)
    if required_permission == Permission.ROLES_WRITE:
        await _guard_role_mutation(request, db_session, user_id)
    if required_permission == Permission.USERS_WRITE:
        await _guard_user_mutation(request, db_session, user_id, permissions)


def _object_reference(instance: Any, state: str) -> dict[str, Any]:
    identifier = getattr(instance, "id", None)
    return {
        "model": type(instance).__name__,
        "id": str(identifier) if identifier is not None else None,
        "state": state,
    }


def _session_change_summary(db_session: AsyncSession) -> dict[str, Any]:
    sync_session = db_session.sync_session
    created = list(sync_session.new)
    changed = list(sync_session.dirty)
    deleted = list(sync_session.deleted)
    items = (
        [_object_reference(item, "created") for item in created]
        + [_object_reference(item, "changed") for item in changed]
        + [_object_reference(item, "deleted") for item in deleted]
    )
    return {
        "created": len(created),
        "changed": len(changed),
        "deleted": len(deleted),
        "items": items[:_MAX_DB_CHANGE_ITEMS],
        "truncated": len(items) > _MAX_DB_CHANGE_ITEMS,
    }


async def _trace_database_step(
    step: str,
    status_value: str,
    *,
    request: Request,
    changes: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        domain="database",
        operation="request_transaction",
        step=step,
        status=status_value,
        severity="error" if status_value == "failed" else "info",
        event_kind="database_transaction",
        component="sqlalchemy",
        direction="internal",
        error_code=error_code,
        message=f"Транзакция БД: {step}",
        input_data={
            "method": request.method,
            "path": request.url.path,
        },
        output_data={"changes": changes or {}},
    )


async def get_db_session(request: Request) -> AsyncSession:  # type: ignore
    db_session = await Database.get_session()
    await _trace_database_step(
        "session_opened",
        "started",
        request=request,
    )
    try:
        await _authorize_control_panel(request, db_session)
        yield db_session  # type: ignore
        changes = _session_change_summary(db_session)
        await _trace_database_step(
            "commit_started",
            "started",
            request=request,
            changes=changes,
        )
        await db_session.commit()
        await _trace_database_step(
            "commit_completed",
            "success",
            request=request,
            changes=changes,
        )
    except Exception as exc:
        changes = _session_change_summary(db_session)
        await db_session.rollback()
        await _trace_database_step(
            "transaction_rolled_back",
            "failed",
            request=request,
            changes=changes,
            error_code=type(exc).__name__,
        )
        raise
    finally:
        await db_session.close()
