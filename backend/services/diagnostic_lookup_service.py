from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.operation_log_event import OperationLogEvent
from models.payments_model import Payment
from models.subscription_model import Subscription
from models.sync_job_model import SyncJob
from models.tariffs_model import TariffPlan
from models.tokens_model import APIToken
from models.users_model import User
from services.operation_context_snapshot_service import build_operation_user_snapshot
from services.operation_log_service import operation_event_payload


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _match(
    kind: str,
    identifier: str,
    *,
    user_id: UUID | None = None,
    label: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": identifier,
        "user_id": str(user_id) if user_id else None,
        "label": label,
        "details": details or {},
    }


async def resolve_diagnostic_query(
    session: AsyncSession,
    query: str,
    *,
    event_limit: int = 100,
) -> dict[str, Any]:
    """Ищет пользователя и трассировку по любому известному идентификатору."""

    normalized = str(query or "").strip()
    if not normalized:
        return {
            "query": normalized,
            "matches": [],
            "user_ids": [],
            "user_contexts": [],
            "operation_ids": [],
            "request_ids": [],
            "events": [],
        }

    lowered = normalized.lower()
    matches: list[dict[str, Any]] = []
    user_ids: set[UUID] = set()
    operation_ids: set[UUID] = set()
    request_ids: set[str] = set()
    parsed_uuid = _uuid(normalized)

    user_result = await session.execute(
        select(User).where(func.lower(User.email) == lowered).limit(1)
    )
    user = user_result.scalar_one_or_none()
    if user is not None:
        user_ids.add(user.id)
        matches.append(
            _match(
                "user",
                str(user.id),
                user_id=user.id,
                label=user.email,
                details={"full_name": user.full_name},
            )
        )

    token_result = await session.execute(
        select(APIToken)
        .where(
            or_(
                func.lower(APIToken.external_account_id) == lowered,
                func.lower(APIToken.label) == lowered,
            )
        )
        .limit(20)
    )
    for token in token_result.scalars().all():
        user_ids.add(token.user_id)
        matches.append(
            _match(
                "marketplace_credential",
                str(token.id),
                user_id=token.user_id,
                label=token.label or token.external_account_id,
                details={
                    "marketplace": getattr(token.marketplace, "value", str(token.marketplace)),
                    "token_type": token.token_type,
                    "is_valid": bool(token.is_valid),
                },
            )
        )

    external_payment_result = await session.execute(
        select(Payment)
        .where(Payment.external_payment_id == normalized)
        .order_by(Payment.created_at.desc())
        .limit(20)
    )
    for payment in external_payment_result.scalars().all():
        user_ids.add(payment.user_id)
        matches.append(
            _match(
                "payment",
                str(payment.id),
                user_id=payment.user_id,
                label=f"{payment.amount} {payment.currency}",
                details={
                    "status": payment.status.value,
                    "provider": payment.provider.value,
                    "external_payment_id": payment.external_payment_id,
                    "tariff_id": str(payment.tariff_id),
                },
            )
        )

    tariff_result = await session.execute(
        select(TariffPlan)
        .where(
            or_(
                func.lower(TariffPlan.code) == lowered,
                func.lower(TariffPlan.name) == lowered,
            )
        )
        .limit(20)
    )
    matched_tariffs = list(tariff_result.scalars().all())
    for tariff in matched_tariffs:
        matches.append(
            _match(
                "tariff",
                str(tariff.id),
                label=tariff.name,
                details={"code": tariff.code, "is_active": bool(tariff.is_active)},
            )
        )
        subscribers_result = await session.execute(
            select(Subscription.user_id)
            .where(Subscription.tariff_id == tariff.id)
            .distinct()
            .limit(50)
        )
        user_ids.update(subscribers_result.scalars().all())

    if parsed_uuid is not None:
        if user is None:
            direct_user = await session.get(User, parsed_uuid)
            if direct_user is not None:
                user_ids.add(direct_user.id)
                matches.append(
                    _match(
                        "user",
                        str(direct_user.id),
                        user_id=direct_user.id,
                        label=direct_user.email,
                        details={"full_name": direct_user.full_name},
                    )
                )

        direct_token = await session.get(APIToken, parsed_uuid)
        if direct_token is not None:
            user_ids.add(direct_token.user_id)
            matches.append(
                _match(
                    "marketplace_credential",
                    str(direct_token.id),
                    user_id=direct_token.user_id,
                    label=direct_token.label or direct_token.external_account_id,
                    details={
                        "marketplace": getattr(
                            direct_token.marketplace,
                            "value",
                            str(direct_token.marketplace),
                        ),
                        "token_type": direct_token.token_type,
                        "is_valid": bool(direct_token.is_valid),
                    },
                )
            )

        payment = await session.get(Payment, parsed_uuid)
        if payment is not None:
            user_ids.add(payment.user_id)
            matches.append(
                _match(
                    "payment",
                    str(payment.id),
                    user_id=payment.user_id,
                    label=f"{payment.amount} {payment.currency}",
                    details={
                        "status": payment.status.value,
                        "provider": payment.provider.value,
                        "external_payment_id": payment.external_payment_id,
                        "tariff_id": str(payment.tariff_id),
                    },
                )
            )

        job = await session.get(SyncJob, parsed_uuid)
        if job is not None:
            user_ids.add(job.user_id)
            matches.append(
                _match(
                    "sync_job",
                    str(job.id),
                    user_id=job.user_id,
                    label=job.entity,
                    details={
                        "status": job.status,
                        "token_id": str(job.token_id),
                        "attempt_count": int(job.attempt_count or 0),
                    },
                )
            )

        subscription = await session.get(Subscription, parsed_uuid)
        if subscription is not None:
            user_ids.add(subscription.user_id)
            matches.append(
                _match(
                    "subscription",
                    str(subscription.id),
                    user_id=subscription.user_id,
                    label=subscription.status.value,
                    details={"tariff_id": str(subscription.tariff_id)},
                )
            )

        if not any(item.id == parsed_uuid for item in matched_tariffs):
            tariff = await session.get(TariffPlan, parsed_uuid)
            if tariff is not None:
                matches.append(
                    _match(
                        "tariff",
                        str(tariff.id),
                        label=tariff.name,
                        details={"code": tariff.code, "is_active": bool(tariff.is_active)},
                    )
                )
                subscribers_result = await session.execute(
                    select(Subscription.user_id)
                    .where(Subscription.tariff_id == tariff.id)
                    .distinct()
                    .limit(50)
                )
                user_ids.update(subscribers_result.scalars().all())

    event_clauses = [
        OperationLogEvent.request_id == normalized,
        OperationLogEvent.subject_id == normalized,
    ]
    if parsed_uuid is not None:
        event_clauses.append(OperationLogEvent.operation_id == parsed_uuid)
        event_clauses.append(OperationLogEvent.user_id == parsed_uuid)
    if user_ids:
        event_clauses.append(OperationLogEvent.user_id.in_(user_ids))

    event_result = await session.execute(
        select(OperationLogEvent)
        .where(or_(*event_clauses))
        .order_by(OperationLogEvent.created_at.desc(), OperationLogEvent.id.desc())
        .limit(max(1, min(event_limit, 500)))
    )
    events = list(event_result.scalars().all())
    for event in events:
        operation_ids.add(event.operation_id)
        if event.request_id:
            request_ids.add(event.request_id)
        if event.user_id:
            user_ids.add(event.user_id)

    sorted_user_ids = sorted(user_ids, key=str)
    user_contexts = [
        await build_operation_user_snapshot(user_id)
        for user_id in sorted_user_ids[:5]
    ]

    return {
        "query": normalized,
        "matches": matches,
        "user_ids": [str(item) for item in sorted_user_ids],
        "user_contexts": user_contexts,
        "contexts_truncated": len(sorted_user_ids) > 5,
        "operation_ids": sorted((str(item) for item in operation_ids)),
        "request_ids": sorted(request_ids),
        "events": [operation_event_payload(item) for item in events],
    }