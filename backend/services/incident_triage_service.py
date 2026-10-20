from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ops_config import ops_config
from models.operation_log_event import OperationLogEvent
from models.payments_model import Payment, PaymentStatus
from models.subscription_model import Subscription
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User


_SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
_ALLOWED_SEVERITIES = frozenset(_SEVERITY_ORDER)
_ATTENTION_STATUSES = {"warning", "failed"}
_ATTENTION_SEVERITIES = {"warning", "error", "critical"}
_EVENT_SCAN_LIMIT = 5000


def _text(value: str | None) -> str:
    return str(value or "").strip()


def _uuid(value: str | None) -> UUID | None:
    try:
        return UUID(_text(value))
    except (TypeError, ValueError):
        return None


def _fingerprint(*parts: object) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _event_severity(event: OperationLogEvent) -> str:
    if event.severity in _ALLOWED_SEVERITIES and event.severity != "info":
        return event.severity
    if event.http_status is not None and event.http_status >= 500:
        return "critical"
    if event.status == "failed" or (
        event.http_status is not None and event.http_status >= 400
    ):
        return "error"
    return "warning"


def _event_code(event: OperationLogEvent) -> str:
    if event.error_code:
        return event.error_code
    if event.http_status is not None and event.http_status >= 400:
        return f"HTTP_{event.http_status}"
    if event.status == "failed":
        return "OPERATION_FAILED"
    if event.status == "warning":
        return "OPERATION_WARNING"
    return f"OPERATION_{_event_severity(event).upper()}"


def _diagnostic_query(
    *,
    user_id: UUID | None = None,
    operation_id: UUID | None = None,
    request_id: str | None = None,
    token_id: UUID | None = None,
    payment_id: UUID | None = None,
    job_id: UUID | None = None,
) -> dict[str, str]:
    if operation_id is not None:
        return {"operation_id": str(operation_id)}
    if request_id:
        return {"request_id": request_id}
    if payment_id is not None:
        return {"payment_query": str(payment_id)}
    if job_id is not None:
        return {"job_query": str(job_id)}
    if token_id is not None:
        return {"token_query": str(token_id)}
    if user_id is not None:
        return {"user_query": str(user_id)}
    return {"attention_only": "1"}


def _incident(
    *,
    code: str,
    severity: str,
    domain: str,
    title: str,
    source: str,
    user_id: UUID | None,
    subject_type: str | None,
    subject_id: str | None,
    first_seen_at: datetime,
    last_seen_at: datetime,
    occurrences: int = 1,
    operation_id: UUID | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    diagnostics: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": _fingerprint(
            source,
            code,
            domain,
            user_id,
            subject_type,
            subject_id,
        ),
        "code": code,
        "severity": severity,
        "domain": domain,
        "title": title,
        "source": source,
        "user_id": str(user_id) if user_id else None,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "operation_id": str(operation_id) if operation_id else None,
        "request_id": request_id,
        "first_seen_at": first_seen_at.isoformat(),
        "last_seen_at": last_seen_at.isoformat(),
        "occurrences": max(1, int(occurrences)),
        "details": details or {},
        "diagnostics": diagnostics or _diagnostic_query(
            user_id=user_id,
            operation_id=operation_id,
            request_id=request_id,
        ),
    }


async def _resolve_user_ids(
    session: AsyncSession,
    query: str | None,
) -> set[UUID] | None:
    normalized = _text(query)
    if not normalized:
        return None

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

    result = await session.execute(
        select(User.id).where(or_(*clauses)).limit(100)
    )
    return set(result.scalars().all())


def _user_clause(model, user_ids: set[UUID] | None):
    if user_ids is None:
        return None
    return model.user_id.in_(user_ids)


async def _operation_incidents(
    session: AsyncSession,
    *,
    cutoff: datetime,
    user_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    statement = select(OperationLogEvent).where(
        OperationLogEvent.created_at >= cutoff,
        or_(
            OperationLogEvent.status.in_(_ATTENTION_STATUSES),
            OperationLogEvent.severity.in_(_ATTENTION_SEVERITIES),
            OperationLogEvent.error_code.is_not(None),
            OperationLogEvent.http_status >= 400,
        ),
    )
    user_clause = _user_clause(OperationLogEvent, user_ids)
    if user_clause is not None:
        statement = statement.where(user_clause)

    statement = statement.order_by(
        OperationLogEvent.created_at.desc(),
        OperationLogEvent.id.desc(),
    ).limit(_EVENT_SCAN_LIMIT)
    events = list((await session.execute(statement)).scalars().all())

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for event in events:
        code = _event_code(event)
        key = (
            event.domain,
            code,
            str(event.user_id or ""),
            str(event.component or ""),
            str(event.subject_type or ""),
            str(event.subject_id or ""),
        )
        current = grouped.get(key)
        if current is None:
            grouped[key] = {
                "event": event,
                "first_seen_at": event.created_at,
                "last_seen_at": event.created_at,
                "occurrences": 1,
            }
            continue
        current["first_seen_at"] = min(current["first_seen_at"], event.created_at)
        current["last_seen_at"] = max(current["last_seen_at"], event.created_at)
        current["occurrences"] += 1

    incidents: list[dict[str, Any]] = []
    for current in grouped.values():
        event: OperationLogEvent = current["event"]
        title = event.message or (
            f"{event.component or event.domain}: {event.step}"
        )
        incidents.append(
            _incident(
                code=_event_code(event),
                severity=_event_severity(event),
                domain=event.domain,
                title=title[:500],
                source="operation_log",
                user_id=event.user_id,
                subject_type=event.subject_type,
                subject_id=event.subject_id,
                first_seen_at=current["first_seen_at"],
                last_seen_at=current["last_seen_at"],
                occurrences=current["occurrences"],
                operation_id=event.operation_id,
                request_id=event.request_id,
                details={
                    "component": event.component,
                    "operation": event.operation,
                    "step": event.step,
                    "provider": event.provider,
                    "http_status": event.http_status,
                    "duration_ms": event.duration_ms,
                },
                diagnostics=_diagnostic_query(
                    user_id=event.user_id,
                    operation_id=event.operation_id,
                    request_id=event.request_id,
                ),
            )
        )
    return incidents


async def _payment_incidents(
    session: AsyncSession,
    *,
    cutoff: datetime,
    user_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    statement = select(Payment).where(Payment.updated_at >= cutoff)
    user_clause = _user_clause(Payment, user_ids)
    if user_clause is not None:
        statement = statement.where(user_clause)
    payments = list((await session.execute(statement)).scalars().all())
    if not payments:
        return []

    payment_ids = {item.id for item in payments}
    subscription_ids = set(
        (
            await session.execute(
                select(Subscription.payment_id).where(
                    Subscription.payment_id.in_(payment_ids)
                )
            )
        ).scalars().all()
    )

    incidents: list[dict[str, Any]] = []
    pending_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for payment in payments:
        created_at = payment.created_at or payment.updated_at
        last_seen = payment.updated_at or created_at

        if payment.status == PaymentStatus.SUCCEEDED and payment.id not in subscription_ids:
            incidents.append(
                _incident(
                    code="PAID_WITHOUT_SUBSCRIPTION",
                    severity="critical",
                    domain="payment",
                    title="Оплата подтверждена, но подписка не активирована",
                    source="payment_state",
                    user_id=payment.user_id,
                    subject_type="payment",
                    subject_id=str(payment.id),
                    first_seen_at=created_at,
                    last_seen_at=last_seen,
                    details={
                        "payment_id": str(payment.id),
                        "provider": payment.provider.value,
                        "mode": payment.mode,
                        "provider_status": payment.provider_status,
                    },
                    diagnostics=_diagnostic_query(
                        user_id=payment.user_id,
                        payment_id=payment.id,
                    ),
                )
            )
            continue

        if payment.status == PaymentStatus.FAILED:
            incidents.append(
                _incident(
                    code="PAYMENT_FAILED",
                    severity="error",
                    domain="payment",
                    title="Платёж завершился отказом или ошибкой",
                    source="payment_state",
                    user_id=payment.user_id,
                    subject_type="payment",
                    subject_id=str(payment.id),
                    first_seen_at=created_at,
                    last_seen_at=last_seen,
                    details={
                        "payment_id": str(payment.id),
                        "provider": payment.provider.value,
                        "mode": payment.mode,
                        "provider_status": payment.provider_status,
                    },
                    diagnostics=_diagnostic_query(
                        user_id=payment.user_id,
                        payment_id=payment.id,
                    ),
                )
            )
            continue

        if (
            payment.status == PaymentStatus.PENDING
            and payment.created_at is not None
            and payment.created_at <= pending_cutoff
        ):
            incidents.append(
                _incident(
                    code="PAYMENT_PENDING_STALE",
                    severity="warning",
                    domain="payment",
                    title="Платёж более суток остаётся в ожидании",
                    source="payment_state",
                    user_id=payment.user_id,
                    subject_type="payment",
                    subject_id=str(payment.id),
                    first_seen_at=created_at,
                    last_seen_at=last_seen,
                    details={
                        "payment_id": str(payment.id),
                        "provider": payment.provider.value,
                        "mode": payment.mode,
                        "provider_status": payment.provider_status,
                    },
                    diagnostics=_diagnostic_query(
                        user_id=payment.user_id,
                        payment_id=payment.id,
                    ),
                )
            )
    return incidents


async def _sync_incidents(
    session: AsyncSession,
    *,
    cutoff: datetime,
    current: datetime,
    user_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    job_statement = select(SyncJob).where(
        or_(
            SyncJob.created_at >= cutoff,
            SyncJob.status == "processing",
        )
    )
    user_clause = _user_clause(SyncJob, user_ids)
    if user_clause is not None:
        job_statement = job_statement.where(user_clause)
    jobs = list((await session.execute(job_statement.limit(3000))).scalars().all())

    state_statement = select(UserSyncState)
    state_user_clause = _user_clause(UserSyncState, user_ids)
    if state_user_clause is not None:
        state_statement = state_statement.where(state_user_clause)
    states = list((await session.execute(state_statement.limit(5000))).scalars().all())

    stale_cutoff = current - timedelta(minutes=ops_config.SYNC_STALE_MINUTES)
    incidents: list[dict[str, Any]] = []

    for job in jobs:
        if job.status == "failed":
            when = job.finished_at or job.started_at or job.created_at
            incidents.append(
                _incident(
                    code="SYNC_JOB_FAILED",
                    severity="error",
                    domain="sync",
                    title=f"Синхронизация {job.entity} завершилась ошибкой",
                    source="sync_job",
                    user_id=job.user_id,
                    subject_type="sync_job",
                    subject_id=str(job.id),
                    first_seen_at=when,
                    last_seen_at=when,
                    occurrences=max(1, int(job.attempt_count or 1)),
                    details={
                        "job_id": str(job.id),
                        "token_id": str(job.token_id),
                        "entity": job.entity,
                        "attempt_count": int(job.attempt_count or 0),
                        "error": job.error,
                    },
                    diagnostics=_diagnostic_query(
                        user_id=job.user_id,
                        job_id=job.id,
                    ),
                )
            )
        elif (
            job.status == "processing"
            and job.lease_expires_at is not None
            and job.lease_expires_at <= current
        ):
            incidents.append(
                _incident(
                    code="SYNC_JOB_LEASE_EXPIRED",
                    severity="critical",
                    domain="sync",
                    title=f"Задача синхронизации {job.entity} потеряла аренду worker",
                    source="sync_job",
                    user_id=job.user_id,
                    subject_type="sync_job",
                    subject_id=str(job.id),
                    first_seen_at=job.started_at or job.created_at,
                    last_seen_at=job.lease_expires_at,
                    details={
                        "job_id": str(job.id),
                        "token_id": str(job.token_id),
                        "entity": job.entity,
                        "lease_expires_at": job.lease_expires_at.isoformat(),
                    },
                    diagnostics=_diagnostic_query(
                        user_id=job.user_id,
                        job_id=job.id,
                    ),
                )
            )

    for state in states:
        when = state.last_sync_at or state.created_at
        if state.last_error:
            incidents.append(
                _incident(
                    code="SYNC_ENTITY_ERROR",
                    severity="error",
                    domain="sync",
                    title=f"Ошибка данных {state.entity}",
                    source="sync_state",
                    user_id=state.user_id,
                    subject_type="marketplace_credential",
                    subject_id=str(state.token_id),
                    first_seen_at=when,
                    last_seen_at=when,
                    details={
                        "token_id": str(state.token_id),
                        "entity": state.entity,
                        "last_error": state.last_error,
                        "last_success_at": (
                            state.last_success_at.isoformat()
                            if state.last_success_at
                            else None
                        ),
                    },
                    diagnostics=_diagnostic_query(
                        user_id=state.user_id,
                        token_id=state.token_id,
                    ),
                )
            )
        elif state.last_success_at is None or state.last_success_at < stale_cutoff:
            incidents.append(
                _incident(
                    code="SYNC_ENTITY_STALE",
                    severity="warning",
                    domain="sync",
                    title=f"Данные {state.entity} давно не обновлялись",
                    source="sync_state",
                    user_id=state.user_id,
                    subject_type="marketplace_credential",
                    subject_id=str(state.token_id),
                    first_seen_at=state.created_at,
                    last_seen_at=state.last_success_at or state.created_at,
                    details={
                        "token_id": str(state.token_id),
                        "entity": state.entity,
                        "last_success_at": (
                            state.last_success_at.isoformat()
                            if state.last_success_at
                            else None
                        ),
                        "stale_after_minutes": ops_config.SYNC_STALE_MINUTES,
                    },
                    diagnostics=_diagnostic_query(
                        user_id=state.user_id,
                        token_id=state.token_id,
                    ),
                )
            )

    return incidents


async def _credential_incidents(
    session: AsyncSession,
    *,
    current: datetime,
    user_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    statement = select(APIToken).where(
        APIToken.is_active.is_(True),
        APIToken.is_revoked.is_(False),
        APIToken.expires_at.is_not(None),
    )
    user_clause = _user_clause(APIToken, user_ids)
    if user_clause is not None:
        statement = statement.where(user_clause)
    tokens = list((await session.execute(statement.limit(3000))).scalars().all())

    warning_at = current + timedelta(days=ops_config.CREDENTIAL_EXPIRY_WARNING_DAYS)
    incidents: list[dict[str, Any]] = []
    for token in tokens:
        if token.expires_at is None:
            continue
        if token.expires_at <= current:
            severity = "error"
            code = "MARKETPLACE_CREDENTIAL_EXPIRED"
            title = "Срок действия подключения маркетплейса истёк"
        elif token.expires_at <= warning_at:
            severity = "warning"
            code = "MARKETPLACE_CREDENTIAL_EXPIRING"
            title = "Срок действия подключения маркетплейса скоро истечёт"
        else:
            continue
        incidents.append(
            _incident(
                code=code,
                severity=severity,
                domain="access",
                title=title,
                source="credential_state",
                user_id=token.user_id,
                subject_type="marketplace_credential",
                subject_id=str(token.id),
                first_seen_at=token.issued_at,
                last_seen_at=current,
                details={
                    "token_id": str(token.id),
                    "marketplace": getattr(
                        token.marketplace,
                        "value",
                        str(token.marketplace),
                    ),
                    "label": token.label,
                    "external_account_id": token.external_account_id,
                    "expires_at": token.expires_at.isoformat(),
                },
                diagnostics=_diagnostic_query(
                    user_id=token.user_id,
                    token_id=token.id,
                ),
            )
        )
    return incidents


def _deduplicate(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in incidents:
        key = item["id"]
        current = result.get(key)
        if current is None:
            result[key] = item
            continue

        current["occurrences"] = int(current.get("occurrences") or 1) + int(
            item.get("occurrences") or 1
        )
        current["first_seen_at"] = min(
            current["first_seen_at"],
            item["first_seen_at"],
        )
        if item["last_seen_at"] > current["last_seen_at"]:
            preserved_occurrences = current["occurrences"]
            result[key] = {**item, "occurrences": preserved_occurrences}
    return list(result.values())


async def _user_labels(
    session: AsyncSession,
    incidents: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    user_ids = {
        UUID(item["user_id"])
        for item in incidents
        if item.get("user_id")
    }
    if not user_ids:
        return {}

    result = await session.execute(
        select(User.id, User.email, User.full_name).where(User.id.in_(user_ids))
    )
    return {
        str(row.id): {
            "email": row.email,
            "full_name": row.full_name,
        }
        for row in result.all()
    }


async def build_incident_feed(
    session: AsyncSession,
    *,
    lookback_hours: int = 72,
    severity: str | None = None,
    domain: str | None = None,
    user_query: str | None = None,
    limit: int = 50,
    offset: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Собирает глобальную очередь проблем из журнала и текущего durable-состояния."""

    current = now or datetime.now(timezone.utc)
    safe_lookback = max(1, min(int(lookback_hours), 24 * 30))
    cutoff = current - timedelta(hours=safe_lookback)
    normalized_severity = _text(severity).lower() or None
    if normalized_severity and normalized_severity not in _ALLOWED_SEVERITIES:
        raise ValueError("Неизвестная важность инцидента")

    user_ids = await _resolve_user_ids(session, user_query)
    if user_ids == set():
        return {
            "generated_at": current.isoformat(),
            "lookback_hours": safe_lookback,
            "items": [],
            "total": 0,
            "limit": max(1, min(int(limit), 200)),
            "offset": max(0, int(offset)),
            "has_more": False,
            "summary": {"critical": 0, "error": 0, "warning": 0, "domains": {}},
            "resolved": {"user_ids": []},
        }

    incidents = [
        *await _operation_incidents(
            session,
            cutoff=cutoff,
            user_ids=user_ids,
        ),
        *await _payment_incidents(
            session,
            cutoff=cutoff,
            user_ids=user_ids,
        ),
        *await _sync_incidents(
            session,
            cutoff=cutoff,
            current=current,
            user_ids=user_ids,
        ),
        *await _credential_incidents(
            session,
            current=current,
            user_ids=user_ids,
        ),
    ]
    incidents = _deduplicate(incidents)

    if normalized_severity:
        incidents = [
            item for item in incidents if item["severity"] == normalized_severity
        ]
    normalized_domain = _text(domain)
    if normalized_domain:
        incidents = [item for item in incidents if item["domain"] == normalized_domain]

    labels = await _user_labels(session, incidents)
    for item in incidents:
        item["user"] = labels.get(item.get("user_id") or "")

    incidents.sort(
        key=lambda item: (
            _SEVERITY_ORDER.get(item["severity"], 9),
            -datetime.fromisoformat(item["last_seen_at"]).timestamp(),
        )
    )

    total = len(incidents)
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))
    page = incidents[safe_offset : safe_offset + safe_limit]

    domains: dict[str, int] = {}
    for item in incidents:
        domains[item["domain"]] = domains.get(item["domain"], 0) + 1

    return {
        "generated_at": current.isoformat(),
        "lookback_hours": safe_lookback,
        "items": page,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(page) < total,
        "summary": {
            "critical": sum(1 for item in incidents if item["severity"] == "critical"),
            "error": sum(1 for item in incidents if item["severity"] == "error"),
            "warning": sum(1 for item in incidents if item["severity"] == "warning"),
            "domains": domains,
        },
        "resolved": {
            "user_ids": sorted(str(item) for item in user_ids)
            if user_ids is not None
            else [],
        },
    }
