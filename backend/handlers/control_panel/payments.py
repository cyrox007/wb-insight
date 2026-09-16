from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.dependencies import get_db_session
from models.payments_model import Payment, PaymentEvent, PaymentProvider, PaymentStatus
from models.tariffs_model import TariffPlan
from models.users_model import User
from services.payment_provider_service import (
    get_provider_runtime,
    list_provider_configs,
    upsert_provider_config,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/control-panel/payments", tags=["Control Panel - Payments"])
_SENSITIVE_FRAGMENTS = ("password", "secret", "token", "credential", "authorization")


def _safe_provider_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if any(fragment in str(key).lower() for fragment in _SENSITIVE_FRAGMENTS) else _safe_provider_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_provider_data(item) for item in value]
    return value


def _payment_item(payment: Payment, email: str | None, tariff_name: str | None) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "user_id": str(payment.user_id),
        "user_email": email,
        "tariff_id": str(payment.tariff_id),
        "tariff_name": tariff_name,
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


@router.get("/providers")
async def providers_list(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    providers = await list_provider_configs(db_session)
    permissions = set(getattr(request.state, "permissions", set()))
    return response_success(
        providers=providers,
        can_manage=Permission.PAYMENTS_WRITE.value in permissions,
    )


@router.put("/providers/{provider}/{mode}")
async def provider_update(
    provider: str,
    mode: str,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Тело запроса должно быть объектом")
        await upsert_provider_config(
            db_session,
            provider=provider,
            mode=mode,
            actor_id=request.state.user_id,
            values=body,
        )
        runtime = await get_provider_runtime(db_session, provider, mode)
        providers = await list_provider_configs(db_session)
    except (TypeError, ValueError, RuntimeError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="PAYMENT_PROVIDER_CONFIG_INVALID", message=str(exc))

    return response_success(
        provider={
            "provider": runtime.provider,
            "mode": runtime.mode,
            "enabled": runtime.enabled,
            "is_default": runtime.is_default,
            "ready": runtime.ready,
        },
        providers=providers,
    )


@router.get("/journal")
async def payment_journal(
    response: Response,
    provider: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    payment_status: str | None = Query(default=None, alias="status"),
    email: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Payment, User.email, TariffPlan.name)
        .join(User, User.id == Payment.user_id)
        .join(TariffPlan, TariffPlan.id == Payment.tariff_id)
        .order_by(Payment.created_at.desc())
    )

    if provider:
        try:
            query = query.where(Payment.provider == PaymentProvider(provider))
        except ValueError:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code="VALIDATION_ERROR", message="Неизвестный provider")
    if payment_status:
        try:
            query = query.where(Payment.status == PaymentStatus(payment_status))
        except ValueError:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code="VALIDATION_ERROR", message="Неизвестный status")
    if mode:
        if mode not in {"test", "live"}:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code="VALIDATION_ERROR", message="mode должен быть test или live")
        query = query.where(Payment.mode == mode)
    if email:
        query = query.where(User.email.ilike(f"%{email.strip()}%"))

    result = await db_session.execute(query.offset(offset).limit(limit + 1))
    rows = result.all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return response_success(
        payments=[_payment_item(payment, user_email, tariff_name) for payment, user_email, tariff_name in rows],
        pagination={"limit": limit, "offset": offset, "has_more": has_more},
    )


@router.get("/journal/{payment_id}")
async def payment_detail(
    payment_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    result = await db_session.execute(
        select(Payment, User.email, TariffPlan.name)
        .join(User, User.id == Payment.user_id)
        .join(TariffPlan, TariffPlan.id == Payment.tariff_id)
        .where(Payment.id == payment_id)
    )
    row = result.first()
    if row is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="PAYMENT_NOT_FOUND", message="Платёж не найден")

    payment, user_email, tariff_name = row
    events_result = await db_session.execute(
        select(PaymentEvent)
        .where(PaymentEvent.payment_id == payment_id)
        .order_by(PaymentEvent.created_at.asc())
    )
    events = [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "provider_status": event.provider_status,
            "provider_data": _safe_provider_data(event.provider_data),
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events_result.scalars().all()
    ]

    detail = _payment_item(payment, user_email, tariff_name)
    detail["provider_data"] = _safe_provider_data(payment.provider_data)
    detail["events"] = events
    return response_success(payment=detail)
