from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from services.diagnostic_lookup_service import resolve_diagnostic_query
from services.operation_filter_service import query_operation_events
from services.operation_log_service import (
    operation_event_payload,
    sanitize_operation_data,
)
from services.operation_trace_query_service import (
    get_complete_operation_trace,
    get_complete_request_trace,
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
    "/diagnostics/search",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def search_diagnostics(
    query: str = Query(min_length=1, max_length=254),
    event_limit: int = Query(default=100, ge=1, le=500),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ищет диагностику по email, пользователю, токену, тарифу, платежу, задаче или ID трассировки."""
    payload = await resolve_diagnostic_query(
        db_session,
        query,
        event_limit=event_limit,
    )
    return sanitize_operation_data(payload)


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
    root_operation_id, operation_ids, events = await get_complete_operation_trace(
        db_session,
        operation_id,
    )
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция в диагностическом журнале не найдена",
        )
    return sanitize_operation_data(
        {
            "requested_operation_id": str(operation_id),
            "root_operation_id": str(root_operation_id),
            "operation_ids": [str(item) for item in operation_ids],
            "events": [operation_event_payload(item) for item in events],
        }
    )


@router.get(
    "/diagnostics/requests/{request_id}",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def get_request_diagnostics(
    request_id: str,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    normalized = str(request_id or "").strip()
    if len(normalized) < 8 or len(normalized) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный request_id",
        )
    root_operation_ids, operation_ids, events = await get_complete_request_trace(
        db_session,
        normalized,
    )
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTTP-запрос в диагностическом журнале не найден",
        )
    return sanitize_operation_data(
        {
            "request_id": normalized,
            "root_operation_ids": [str(item) for item in root_operation_ids],
            "operation_ids": [str(item) for item in operation_ids],
            "events": [operation_event_payload(item) for item in events],
        }
    )


@router.get(
    "/diagnostics/events",
    dependencies=[Depends(require_permission(Permission.DIAGNOSTICS_READ))],
)
async def list_diagnostic_events(
    operation_id: UUID | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    user_query: str | None = Query(default=None, max_length=254),
    token_query: str | None = Query(default=None, max_length=255),
    payment_query: str | None = Query(default=None, max_length=255),
    tariff_query: str | None = Query(default=None, max_length=255),
    job_query: str | None = Query(default=None, max_length=255),
    domain: str | None = Query(default=None, max_length=32),
    operation: str | None = Query(default=None, max_length=64),
    event_status: str | None = Query(default=None, alias="status", max_length=16),
    severity: str | None = Query(default=None, max_length=16),
    component: str | None = Query(default=None, max_length=96),
    event_kind: str | None = Query(default=None, max_length=32),
    direction: str | None = Query(default=None, max_length=16),
    request_id: str | None = Query(default=None, max_length=64),
    subject_type: str | None = Query(default=None, max_length=64),
    subject_id: str | None = Query(default=None, max_length=160),
    provider: str | None = Query(default=None, max_length=64),
    http_statuses: str | None = Query(default=None, max_length=64),
    http_status_group: str | None = Query(default=None, max_length=16),
    error_code: str | None = Query(default=None, max_length=96),
    min_duration_ms: int | None = Query(default=None, ge=0, le=3_600_000),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    attention_only: bool = Query(default=False),
    unfinished_only: bool = Query(default=False),
    retry_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Фильтрует операционный журнал по пользователю, объектам и техническим признакам."""

    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Начало периода не может быть позже конца периода",
        )

    try:
        payload = await query_operation_events(
            db_session,
            operation_id=operation_id,
            user_id=user_id,
            actor_user_id=actor_user_id,
            user_query=user_query,
            token_query=token_query,
            payment_query=payment_query,
            tariff_query=tariff_query,
            job_query=job_query,
            domain=domain,
            operation=operation,
            status=event_status,
            severity=severity,
            component=component,
            event_kind=event_kind,
            direction=direction,
            request_id=request_id,
            subject_type=subject_type,
            subject_id=subject_id,
            provider=provider,
            http_statuses=http_statuses,
            http_status_group=http_status_group,
            error_code=error_code,
            min_duration_ms=min_duration_ms,
            created_from=created_from,
            created_to=created_to,
            attention_only=attention_only,
            unfinished_only=unfinished_only,
            retry_only=retry_only,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return sanitize_operation_data(payload)
