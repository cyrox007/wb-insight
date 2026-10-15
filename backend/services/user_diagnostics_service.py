from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ops_config import ops_config
from models.payments_model import Payment, PaymentEvent, PaymentStatus
from models.subscription_model import Subscription, SubscriptionStatus
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User
from services.operation_log_service import list_operation_events, operation_event_payload


async def find_user_for_diagnostics(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    email: str | None = None,
) -> User | None:
    if user_id is not None:
        return await session.get(User, user_id)
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    return result.scalar_one_or_none()


def _payment_payload(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "tariff_id": str(payment.tariff_id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status.value,
        "provider": payment.provider.value,
        "mode": payment.mode,
        "external_payment_id": payment.external_payment_id,
        "provider_status": payment.provider_status,
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
    }


def _payment_event_payload(event: PaymentEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "provider_status": event.provider_status,
        "provider_data": event.provider_data or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _credential_payload(token: APIToken) -> dict[str, Any]:
    marketplace = getattr(token.marketplace, "value", str(token.marketplace))
    return {
        "id": str(token.id),
        "marketplace": marketplace,
        "token_type": token.token_type,
        "external_account_id": token.external_account_id,
        "label": token.label,
        "issued_at": token.issued_at.isoformat() if token.issued_at else None,
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "is_active": bool(token.is_active),
        "is_revoked": bool(token.is_revoked),
        "is_expired": token.is_expired,
        "is_valid": token.is_valid,
    }


def _sync_state_payload(state: UserSyncState) -> dict[str, Any]:
    return {
        "id": str(state.id),
        "token_id": str(state.token_id),
        "entity": state.entity,
        "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
        "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
        "source_cursor": state.source_cursor or {},
        "last_error": state.last_error,
    }


def _sync_job_payload(job: SyncJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "token_id": str(job.token_id),
        "entity": job.entity,
        "status": job.status,
        "attempt_count": int(job.attempt_count or 0),
        "is_active": bool(job.is_active),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "available_at": job.available_at.isoformat() if job.available_at else None,
        "lease_expires_at": job.lease_expires_at.isoformat() if job.lease_expires_at else None,
        "error": job.error,
        "checkpoint": {
            key: value
            for key, value in (job.payload or {}).items()
            if key in {"dateFrom", "completedThrough", "page", "offset", "cursor", "total", "processed", "saved"}
        },
    }


def _subscription_payload(subscription: Subscription) -> dict[str, Any]:
    return {
        "id": str(subscription.id),
        "tariff_id": str(subscription.tariff_id),
        "payment_id": str(subscription.payment_id) if subscription.payment_id else None,
        "status": subscription.status.value,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "cancel_at_period_end": bool(subscription.cancel_at_period_end),
    }


def _anomaly(
    code: str,
    severity: str,
    title: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "details": details,
    }


def _payment_anomalies(
    payments: list[Payment],
    subscriptions: list[Subscription],
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    subscription_payment_ids = {
        item.payment_id for item in subscriptions if item.payment_id is not None
    }
    for payment in payments:
        if payment.status == PaymentStatus.SUCCEEDED and payment.id not in subscription_payment_ids:
            anomalies.append(
                _anomaly(
                    "PAID_WITHOUT_SUBSCRIPTION",
                    "critical",
                    "Оплата подтверждена, но подписка не найдена",
                    {"payment_id": str(payment.id)},
                )
            )
        if payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
            anomalies.append(
                _anomaly(
                    "PAYMENT_NOT_COMPLETED",
                    "warning",
                    "Платёжная попытка завершилась без оплаты",
                    {
                        "payment_id": str(payment.id),
                        "status": payment.status.value,
                        "provider_status": payment.provider_status,
                    },
                )
            )
    return anomalies


def _credential_anomalies(tokens: list[APIToken]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for token in tokens:
        if token.is_revoked or token.is_expired or not token.is_active:
            anomalies.append(
                _anomaly(
                    "MARKETPLACE_CREDENTIAL_UNAVAILABLE",
                    "error",
                    "Подключение маркетплейса недоступно",
                    {
                        "token_id": str(token.id),
                        "label": token.label,
                        "revoked": bool(token.is_revoked),
                        "expired": token.is_expired,
                        "active": bool(token.is_active),
                    },
                )
            )
    return anomalies


def _sync_anomalies(
    states: list[UserSyncState],
    jobs: list[SyncJob],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    stale_cutoff = now - timedelta(minutes=ops_config.SYNC_STALE_MINUTES)
    for state in states:
        if state.last_error:
            anomalies.append(
                _anomaly(
                    "SYNC_ENTITY_ERROR",
                    "error",
                    "Ошибка синхронизации набора данных",
                    {
                        "token_id": str(state.token_id),
                        "entity": state.entity,
                        "error": state.last_error,
                    },
                )
            )
        elif state.last_success_at is None or state.last_success_at < stale_cutoff:
            anomalies.append(
                _anomaly(
                    "SYNC_ENTITY_STALE",
                    "warning",
                    "Данные давно не обновлялись",
                    {
                        "token_id": str(state.token_id),
                        "entity": state.entity,
                        "last_success_at": (
                            state.last_success_at.isoformat()
                            if state.last_success_at
                            else None
                        ),
                    },
                )
            )
    for job in jobs:
        if job.status == "failed":
            anomalies.append(
                _anomaly(
                    "SYNC_JOB_FAILED",
                    "error",
                    "Фоновая задача синхронизации завершилась ошибкой",
                    {
                        "job_id": str(job.id),
                        "token_id": str(job.token_id),
                        "entity": job.entity,
                        "attempt_count": int(job.attempt_count or 0),
                        "error": job.error,
                    },
                )
            )
        if (
            job.status == "processing"
            and job.lease_expires_at is not None
            and job.lease_expires_at <= now
        ):
            anomalies.append(
                _anomaly(
                    "SYNC_JOB_LEASE_EXPIRED",
                    "critical",
                    "Задача синхронизации зависла без активной аренды",
                    {"job_id": str(job.id), "entity": job.entity},
                )
            )
    return anomalies


async def build_user_diagnostics(
    session: AsyncSession,
    user: User,
    *,
    event_limit: int = 150,
    job_limit: int = 100,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)

    payments = list(
        (
            await session.execute(
                select(Payment)
                .where(Payment.user_id == user.id)
                .order_by(desc(Payment.created_at))
                .limit(50)
            )
        ).scalars().all()
    )
    payment_ids = [item.id for item in payments]
    payment_events: list[PaymentEvent] = []
    if payment_ids:
        payment_events = list(
            (
                await session.execute(
                    select(PaymentEvent)
                    .where(PaymentEvent.payment_id.in_(payment_ids))
                    .order_by(PaymentEvent.created_at, PaymentEvent.id)
                )
            ).scalars().all()
        )

    subscriptions = list(
        (
            await session.execute(
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .order_by(desc(Subscription.created_at))
            )
        ).scalars().all()
    )
    tokens = list(
        (
            await session.execute(
                select(APIToken)
                .where(APIToken.user_id == user.id)
                .order_by(desc(APIToken.issued_at))
            )
        ).scalars().all()
    )
    states = list(
        (
            await session.execute(
                select(UserSyncState)
                .where(UserSyncState.user_id == user.id)
                .order_by(UserSyncState.token_id, UserSyncState.entity)
            )
        ).scalars().all()
    )
    jobs = list(
        (
            await session.execute(
                select(SyncJob)
                .where(SyncJob.user_id == user.id)
                .order_by(desc(SyncJob.created_at))
                .limit(max(1, min(job_limit, 300)))
            )
        ).scalars().all()
    )
    operation_events = await list_operation_events(
        session,
        user_id=user.id,
        limit=max(1, min(event_limit, 500)),
    )

    events_by_payment: dict[UUID, list[dict[str, Any]]] = {}
    for event in payment_events:
        events_by_payment.setdefault(event.payment_id, []).append(
            _payment_event_payload(event)
        )

    anomalies = [
        *_payment_anomalies(payments, subscriptions),
        *_credential_anomalies(tokens),
        *_sync_anomalies(states, jobs, now=current),
    ]
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    anomalies.sort(key=lambda item: severity_order.get(item["severity"], 9))

    active_subscriptions = [
        item
        for item in subscriptions
        if item.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.DEMO}
        and item.current_period_start <= current < item.current_period_end
    ]

    return {
        "generated_at": current.isoformat(),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "inn": user.inn,
            "is_active": bool(user.is_active),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "summary": {
            "anomalies": len(anomalies),
            "critical": sum(1 for item in anomalies if item["severity"] == "critical"),
            "failed_payments": sum(1 for item in payments if item.status == PaymentStatus.FAILED),
            "active_subscriptions": len(active_subscriptions),
            "credentials": len(tokens),
            "valid_credentials": sum(1 for item in tokens if item.is_valid),
            "sync_entities": len(states),
            "sync_errors": sum(1 for item in states if item.last_error),
            "failed_jobs": sum(1 for item in jobs if item.status == "failed"),
        },
        "anomalies": anomalies,
        "payments": [
            {
                **_payment_payload(payment),
                "events": events_by_payment.get(payment.id, []),
            }
            for payment in payments
        ],
        "subscriptions": [_subscription_payload(item) for item in subscriptions],
        "credentials": [_credential_payload(item) for item in tokens],
        "sync_states": [_sync_state_payload(item) for item in states],
        "sync_jobs": [_sync_job_payload(item) for item in jobs],
        "operation_timeline": [operation_event_payload(item) for item in operation_events],
    }
