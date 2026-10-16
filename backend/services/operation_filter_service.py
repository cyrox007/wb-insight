from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.operation_log_event import OperationLogEvent
from models.payments_model import Payment
from models.subscription_model import Subscription
from models.sync_job_model import SyncJob
from models.tariffs_model import TariffPlan
from models.tokens_model import APIToken
from models.users_model import User
from services.operation_log_service import operation_event_payload


_ALLOWED_HTTP_GROUPS = {"2xx", "3xx", "4xx", "5xx", "errors"}
_TERMINAL_OPERATION_STATUSES = {"success", "failed"}
_ATTENTION_STATUSES = {"warning", "failed"}
_ATTENTION_SEVERITIES = {"warning", "error", "critical"}


def _uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value).strip())
    except (TypeError, ValueError):
        return None


def _text(value: str | None) -> str:
    return str(value or "").strip()


def parse_http_statuses(value: str | None) -> tuple[int, ...]:
    """Разбирает список HTTP-кодов вида ``401,403,429``."""

    normalized = _text(value)
    if not normalized:
        return ()

    result: list[int] = []
    for raw_item in normalized.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if not item.isdigit():
            raise ValueError("HTTP-коды должны быть числами через запятую")
        code = int(item)
        if code < 100 or code > 599:
            raise ValueError("HTTP-код должен быть в диапазоне от 100 до 599")
        if code not in result:
            result.append(code)
    return tuple(result)


def validate_http_status_group(value: str | None) -> str | None:
    normalized = _text(value).lower()
    if not normalized:
        return None
    if normalized not in _ALLOWED_HTTP_GROUPS:
        allowed = ", ".join(sorted(_ALLOWED_HTTP_GROUPS))
        raise ValueError(f"Неизвестная группа HTTP-кодов. Допустимо: {allowed}")
    return normalized


async def _resolve_user_ids(session: AsyncSession, query: str | None) -> set[UUID]:
    normalized = _text(query)
    if not normalized:
        return set()

    lowered = normalized.lower()
    parsed_uuid = _uuid(normalized)
    clauses = [
        func.lower(User.email).contains(lowered),
        func.lower(User.full_name).contains(lowered),
        User.phone.contains(normalized),
        User.inn == normalized,
    ]
    if parsed_uuid is not None:
        clauses.append(User.id == parsed_uuid)

    result = await session.execute(select(User.id).where(or_(*clauses)).limit(100))
    return set(result.scalars().all())


async def _resolve_token_ids(session: AsyncSession, query: str | None) -> set[UUID]:
    normalized = _text(query)
    if not normalized:
        return set()

    lowered = normalized.lower()
    parsed_uuid = _uuid(normalized)
    clauses = [
        func.lower(func.coalesce(APIToken.label, "")).contains(lowered),
        func.lower(func.coalesce(APIToken.external_account_id, "")).contains(lowered),
    ]
    if parsed_uuid is not None:
        clauses.append(APIToken.id == parsed_uuid)

    result = await session.execute(select(APIToken.id).where(or_(*clauses)).limit(100))
    return set(result.scalars().all())


async def _resolve_payment_ids(session: AsyncSession, query: str | None) -> set[UUID]:
    normalized = _text(query)
    if not normalized:
        return set()

    parsed_uuid = _uuid(normalized)
    clauses = [
        func.lower(func.coalesce(Payment.external_payment_id, "")).contains(
            normalized.lower()
        )
    ]
    if parsed_uuid is not None:
        clauses.append(Payment.id == parsed_uuid)

    result = await session.execute(select(Payment.id).where(or_(*clauses)).limit(100))
    return set(result.scalars().all())


async def _resolve_job_ids(session: AsyncSession, query: str | None) -> set[UUID]:
    normalized = _text(query)
    if not normalized:
        return set()

    parsed_uuid = _uuid(normalized)
    clauses = [func.lower(SyncJob.entity).contains(normalized.lower())]
    if parsed_uuid is not None:
        clauses.append(SyncJob.id == parsed_uuid)

    result = await session.execute(select(SyncJob.id).where(or_(*clauses)).limit(200))
    return set(result.scalars().all())


async def _resolve_tariff_ids(session: AsyncSession, query: str | None) -> set[UUID]:
    normalized = _text(query)
    if not normalized:
        return set()

    parsed_uuid = _uuid(normalized)
    lowered = normalized.lower()
    clauses = [
        func.lower(TariffPlan.code).contains(lowered),
        func.lower(TariffPlan.name).contains(lowered),
    ]
    if parsed_uuid is not None:
        clauses.append(TariffPlan.id == parsed_uuid)

    result = await session.execute(select(TariffPlan.id).where(or_(*clauses)).limit(100))
    return set(result.scalars().all())


async def _job_ids_for_tokens(session: AsyncSession, token_ids: set[UUID]) -> set[UUID]:
    if not token_ids:
        return set()
    result = await session.execute(
        select(SyncJob.id).where(SyncJob.token_id.in_(token_ids)).limit(2000)
    )
    return set(result.scalars().all())


async def _operation_ids_for_subjects(
    session: AsyncSession,
    subject_ids: set[str],
) -> set[UUID]:
    if not subject_ids:
        return set()
    result = await session.execute(
        select(OperationLogEvent.operation_id)
        .where(OperationLogEvent.subject_id.in_(subject_ids))
        .distinct()
        .limit(5000)
    )
    return set(result.scalars().all())


async def _tariff_user_ids(session: AsyncSession, tariff_ids: set[UUID]) -> set[UUID]:
    if not tariff_ids:
        return set()
    result = await session.execute(
        select(Subscription.user_id)
        .where(Subscription.tariff_id.in_(tariff_ids))
        .distinct()
        .limit(5000)
    )
    return set(result.scalars().all())


async def _tariff_payment_ids(session: AsyncSession, tariff_ids: set[UUID]) -> set[UUID]:
    if not tariff_ids:
        return set()
    result = await session.execute(
        select(Payment.id).where(Payment.tariff_id.in_(tariff_ids)).limit(5000)
    )
    return set(result.scalars().all())


def _http_group_clause(group: str):
    if group == "2xx":
        return OperationLogEvent.http_status.between(200, 299)
    if group == "3xx":
        return OperationLogEvent.http_status.between(300, 399)
    if group == "4xx":
        return OperationLogEvent.http_status.between(400, 499)
    if group == "5xx":
        return OperationLogEvent.http_status.between(500, 599)
    return OperationLogEvent.http_status >= 400


def _attention_clause():
    return or_(
        OperationLogEvent.status.in_(_ATTENTION_STATUSES),
        OperationLogEvent.severity.in_(_ATTENTION_SEVERITIES),
        OperationLogEvent.error_code.is_not(None),
        OperationLogEvent.http_status >= 400,
    )


def _unfinished_clause():
    started_operations = select(OperationLogEvent.operation_id).where(
        OperationLogEvent.status == "started"
    )
    terminal_operations = select(OperationLogEvent.operation_id).where(
        OperationLogEvent.status.in_(_TERMINAL_OPERATION_STATUSES)
    )
    return and_(
        OperationLogEvent.operation_id.in_(started_operations),
        ~OperationLogEvent.operation_id.in_(terminal_operations),
    )


def _retry_clause():
    return or_(
        OperationLogEvent.step.ilike("%retry%"),
        OperationLogEvent.operation.ilike("%retry%"),
        OperationLogEvent.message.ilike("%повтор%"),
    )


async def query_operation_events(
    session: AsyncSession,
    *,
    operation_id: UUID | None = None,
    user_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    user_query: str | None = None,
    token_query: str | None = None,
    payment_query: str | None = None,
    tariff_query: str | None = None,
    job_query: str | None = None,
    domain: str | None = None,
    operation: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    component: str | None = None,
    event_kind: str | None = None,
    direction: str | None = None,
    request_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    provider: str | None = None,
    http_statuses: str | None = None,
    http_status_group: str | None = None,
    error_code: str | None = None,
    min_duration_ms: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    attention_only: bool = False,
    unfinished_only: bool = False,
    retry_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Возвращает события журнала по комбинируемым серверным фильтрам."""

    statuses = parse_http_statuses(http_statuses)
    status_group = validate_http_status_group(http_status_group)
    statement = select(OperationLogEvent)

    if operation_id is not None:
        statement = statement.where(OperationLogEvent.operation_id == operation_id)
    if user_id is not None:
        statement = statement.where(OperationLogEvent.user_id == user_id)
    if actor_user_id is not None:
        statement = statement.where(OperationLogEvent.actor_user_id == actor_user_id)

    resolved: dict[str, list[str]] = {}

    if _text(user_query):
        user_ids = await _resolve_user_ids(session, user_query)
        resolved["user_ids"] = sorted(str(item) for item in user_ids)
        statement = statement.where(
            OperationLogEvent.user_id.in_(user_ids) if user_ids else false()
        )

    if _text(token_query):
        token_ids = await _resolve_token_ids(session, token_query)
        job_ids = await _job_ids_for_tokens(session, token_ids)
        related_subjects = {str(item) for item in token_ids | job_ids}
        operation_ids = await _operation_ids_for_subjects(session, related_subjects)
        resolved["token_ids"] = sorted(str(item) for item in token_ids)
        resolved["token_job_ids"] = sorted(str(item) for item in job_ids)
        statement = statement.where(
            OperationLogEvent.operation_id.in_(operation_ids)
            if operation_ids
            else false()
        )

    if _text(payment_query):
        payment_ids = await _resolve_payment_ids(session, payment_query)
        operation_ids = await _operation_ids_for_subjects(
            session,
            {str(item) for item in payment_ids},
        )
        resolved["payment_ids"] = sorted(str(item) for item in payment_ids)
        statement = statement.where(
            OperationLogEvent.operation_id.in_(operation_ids)
            if operation_ids
            else false()
        )

    if _text(job_query):
        job_ids = await _resolve_job_ids(session, job_query)
        operation_ids = await _operation_ids_for_subjects(
            session,
            {str(item) for item in job_ids},
        )
        resolved["job_ids"] = sorted(str(item) for item in job_ids)
        statement = statement.where(
            OperationLogEvent.operation_id.in_(operation_ids)
            if operation_ids
            else false()
        )

    if _text(tariff_query):
        tariff_ids = await _resolve_tariff_ids(session, tariff_query)
        tariff_users = await _tariff_user_ids(session, tariff_ids)
        tariff_payments = await _tariff_payment_ids(session, tariff_ids)
        payment_operations = await _operation_ids_for_subjects(
            session,
            {str(item) for item in tariff_payments},
        )
        resolved["tariff_ids"] = sorted(str(item) for item in tariff_ids)
        statement = statement.where(
            or_(
                OperationLogEvent.user_id.in_(tariff_users),
                OperationLogEvent.operation_id.in_(payment_operations),
            )
            if tariff_ids
            else false()
        )

    if _text(domain):
        statement = statement.where(OperationLogEvent.domain == _text(domain))
    if _text(operation):
        statement = statement.where(OperationLogEvent.operation == _text(operation))
    if _text(status):
        statement = statement.where(OperationLogEvent.status == _text(status))
    if _text(severity):
        statement = statement.where(OperationLogEvent.severity == _text(severity))
    if _text(component):
        statement = statement.where(OperationLogEvent.component.ilike(f"%{_text(component)}%"))
    if _text(event_kind):
        statement = statement.where(OperationLogEvent.event_kind == _text(event_kind))
    if _text(direction):
        statement = statement.where(OperationLogEvent.direction == _text(direction))
    if _text(request_id):
        statement = statement.where(OperationLogEvent.request_id == _text(request_id))
    if _text(subject_type):
        statement = statement.where(OperationLogEvent.subject_type == _text(subject_type))
    if _text(subject_id):
        statement = statement.where(OperationLogEvent.subject_id == _text(subject_id))
    if _text(provider):
        statement = statement.where(OperationLogEvent.provider == _text(provider))
    if statuses:
        statement = statement.where(OperationLogEvent.http_status.in_(statuses))
    if status_group:
        statement = statement.where(_http_group_clause(status_group))
    if _text(error_code):
        statement = statement.where(
            OperationLogEvent.error_code.ilike(f"%{_text(error_code)}%")
        )
    if min_duration_ms is not None:
        statement = statement.where(OperationLogEvent.duration_ms >= max(0, min_duration_ms))
    if created_from is not None:
        statement = statement.where(OperationLogEvent.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(OperationLogEvent.created_at <= created_to)
    if attention_only:
        statement = statement.where(_attention_clause())
    if unfinished_only:
        statement = statement.where(_unfinished_clause())
    if retry_only:
        statement = statement.where(_retry_clause())

    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await session.execute(count_statement)).scalar_one() or 0)

    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    statement = statement.order_by(
        OperationLogEvent.created_at.desc(),
        OperationLogEvent.id.desc(),
    )
    statement = statement.limit(safe_limit).offset(safe_offset)
    events = list((await session.execute(statement)).scalars().all())

    return {
        "items": [operation_event_payload(item) for item in events],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(events) < total,
        "resolved": resolved,
    }
