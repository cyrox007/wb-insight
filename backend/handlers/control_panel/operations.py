from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from services.operation_log_service import (
    get_operation_timeline,
    list_operation_events,
    operation_event_payload,
    sanitize_operation_data,
)
from services.operational_monitoring_service import build_operational_snapshot
from services.user_diagnostics_service import (
    build_user_diagnostics,
    find_user_for_diagnostics,
)


router = APIRouter(
    prefix="/control-panel/operations",
    tags=["Панель управления — диагностика"],
)


@router.get(
    "/health",
    dependencies=[Depends(require_permission(Permission.SYSTEM_MANAGE))],
)
async def get_operational_health(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Возвращает агрегированное техническое состояние без секретов продавцов."""
    return await build_operational_snapshot(db_session)


@router.get(
    "/diagnostics/users",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def find_user_diagnostics(
    user_id: UUID | None = Query(default=None),
    email: str | None = Query(default=None, max_length=254),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    if user_id is None and not str(email or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите user_id или email пользователя",
        )
    user = await find_user_for_diagnostics(
        db_session,
        user_id=user_id,
        email=email,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь для диагностики не найден",
        )
    payload = await build_user_diagnostics(db_session, user)
    return sanitize_operation_data(payload)


@router.get(
    "/diagnostics/users/{user_id}",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def get_user_diagnostics(
    user_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user = await find_user_for_diagnostics(db_session, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь для диагностики не найден",
        )
    payload = await build_user_diagnostics(db_session, user)
    return sanitize_operation_data(payload)


@router.get(
    "/diagnostics/operations/{operation_id}",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def get_operation_diagnostics(
    operation_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    events = await get_operation_timeline(db_session, operation_id)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция в диагностическом журнале не найдена",
        )
    return sanitize_operation_data(
        {
            "operation_id": str(operation_id),
            "events": [operation_event_payload(item) for item in events],
        }
    )


@router.get(
    "/diagnostics/events",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def list_diagnostic_events(
    user_id: UUID | None = Query(default=None),
    domain: str | None = Query(default=None, max_length=32),
    event_status: str | None = Query(default=None, alias="status", max_length=16),
    severity: str | None = Query(default=None, max_length=16),
    request_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    events = await list_operation_events(
        db_session,
        user_id=user_id,
        domain=domain,
        status=event_status,
        severity=severity,
        request_id=request_id,
        limit=limit,
        offset=offset,
    )
    return sanitize_operation_data(
        {
            "items": [operation_event_payload(item) for item in events],
            "limit": limit,
            "offset": offset,
        }
    )
