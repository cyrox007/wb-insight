from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.sber.client import SberOrderStatus
from models.payments_model import (
    Payment,
    PaymentEvent,
    PaymentProvider,
    PaymentStatus,
)
from services.subscription_service import (
    create_subscription,
    deactivate_active_subscriptions,
    get_subscription_by_payment_id,
)


async def create_payment(
    session: AsyncSession,
    *,
    user_id: UUID,
    tariff_id: UUID,
    amount: Decimal,
    provider: PaymentProvider,
    idempotency_key: str | None = None,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=amount,
        currency="RUB",
        status=PaymentStatus.PENDING,
        provider=provider,
        idempotency_key=idempotency_key,
        external_payment_id=None,
        provider_status=None,
        provider_data=None,
        confirmed_at=None,
    )
    session.add(payment)
    await session.flush()
    return payment


async def create_or_get_payment(
    session: AsyncSession,
    *,
    user_id: UUID,
    tariff_id: UUID,
    amount: Decimal,
    provider: PaymentProvider,
    idempotency_key: str,
) -> tuple[Payment, bool]:
    existing = await get_payment_by_idempotency_key(
        session,
        user_id=user_id,
        provider=provider,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if existing.tariff_id != tariff_id or Decimal(existing.amount) != amount:
            raise ValueError("Idempotency-Key уже использован для другого платежа")
        return existing, False

    payment = Payment(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=amount,
        currency="RUB",
        status=PaymentStatus.PENDING,
        provider=provider,
        idempotency_key=idempotency_key,
        external_payment_id=None,
        provider_status=None,
        provider_data=None,
        confirmed_at=None,
    )
    try:
        async with session.begin_nested():
            session.add(payment)
            await session.flush()
        return payment, True
    except IntegrityError:
        existing = await get_payment_by_idempotency_key(
            session,
            user_id=user_id,
            provider=provider,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            raise
        if existing.tariff_id != tariff_id or Decimal(existing.amount) != amount:
            raise ValueError("Idempotency-Key уже использован для другого платежа")
        return existing, False


async def get_payment(
    session: AsyncSession,
    payment_id: UUID,
) -> Optional[Payment]:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def get_payment_for_update(
    session: AsyncSession,
    payment_id: UUID,
) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_payment_by_external_id(
    session: AsyncSession,
    *,
    provider: PaymentProvider,
    external_payment_id: str,
) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(
            Payment.provider == provider,
            Payment.external_payment_id == external_payment_id,
        )
    )
    return result.scalar_one_or_none()


async def get_payment_by_idempotency_key(
    session: AsyncSession,
    *,
    user_id: UUID,
    provider: PaymentProvider,
    idempotency_key: str,
) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(
            Payment.user_id == user_id,
            Payment.provider == provider,
            Payment.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def record_payment_event(
    session: AsyncSession,
    *,
    payment_id: UUID,
    event_type: str,
    provider_status: str | None = None,
    provider_data: dict[str, Any] | None = None,
) -> PaymentEvent:
    event = PaymentEvent(
        payment_id=payment_id,
        event_type=event_type,
        provider_status=provider_status,
        provider_data=provider_data,
    )
    session.add(event)
    await session.flush()
    return event


async def mark_payment_succeeded(
    session: AsyncSession,
    payment: Payment,
    provider_data: dict[str, Any] | None = None,
) -> Payment:
    if payment.status == PaymentStatus.SUCCEEDED:
        return payment
    if payment.status not in {PaymentStatus.PENDING, PaymentStatus.SUCCEEDED}:
        raise ValueError("Нельзя подтвердить платёж в текущем статусе")

    payment.status = PaymentStatus.SUCCEEDED
    payment.provider_data = provider_data or payment.provider_data
    payment.confirmed_at = payment.confirmed_at or datetime.now(timezone.utc)
    payment.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return payment


async def mark_payment_failed(
    session: AsyncSession,
    payment: Payment,
    provider_data: dict[str, Any] | None = None,
) -> Payment:
    if payment.status == PaymentStatus.SUCCEEDED:
        raise ValueError("Успешный платёж нельзя перевести в failed")
    payment.status = PaymentStatus.FAILED
    payment.provider_data = provider_data or payment.provider_data
    payment.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return payment


def normalize_sber_status(status: SberOrderStatus) -> str:
    return f"{status.order_status if status.order_status is not None else 'unknown'}:{status.payment_state or 'UNKNOWN'}"


def safe_sber_provider_data(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "errorCode",
        "errorMessage",
        "orderId",
        "orderNumber",
        "orderStatus",
        "paymentState",
        "amount",
        "currency",
        "actionCode",
        "actionCodeDescription",
        "date",
        "formUrl",
        "externalParams",
    }
    return {key: value for key, value in data.items() if key in allowed}


async def apply_sber_status(
    session: AsyncSession,
    *,
    payment_id: UUID,
    status: SberOrderStatus,
    event_type: str = "status_checked",
) -> tuple[Payment, object | None]:
    """Apply bank-confirmed state exactly once and activate a subscription once."""

    payment = await get_payment_for_update(session, payment_id)
    if payment is None:
        raise ValueError("Платёж не найден")
    if payment.provider != PaymentProvider.SBER:
        raise ValueError("Платёж создан другим провайдером")

    normalized = normalize_sber_status(status)
    safe_data = safe_sber_provider_data(status.raw)
    payment.provider_status = normalized
    payment.provider_data = {
        **(payment.provider_data or {}),
        "last_status": safe_data,
    }
    payment.updated_at = datetime.now(timezone.utc)

    await record_payment_event(
        session,
        payment_id=payment.id,
        event_type=event_type,
        provider_status=normalized,
        provider_data=safe_data,
    )

    existing_subscription = await get_subscription_by_payment_id(session, payment.id)
    if payment.status == PaymentStatus.SUCCEEDED:
        await session.flush()
        return payment, existing_subscription

    if status.is_paid:
        payment.status = PaymentStatus.SUCCEEDED
        payment.confirmed_at = datetime.now(timezone.utc)
        if existing_subscription is None:
            await deactivate_active_subscriptions(session, payment.user_id)
            existing_subscription = await create_subscription(
                session,
                payment.user_id,
                payment.tariff_id,
                payment_id=payment.id,
            )
    elif status.order_status == 6:
        payment.status = PaymentStatus.FAILED
    elif status.order_status in {3, 4}:
        payment.status = PaymentStatus.CANCELLED

    await session.flush()
    return payment, existing_subscription


async def fake_pay(session: AsyncSession, payment_id: UUID) -> Payment:
    payment = await get_payment(session, payment_id)
    if payment is None:
        raise ValueError("Платёж не найден")
    if payment.provider != PaymentProvider.FAKE:
        raise ValueError("Этот платёж нельзя подтвердить fake-провайдером")
    return await mark_payment_succeeded(
        session,
        payment,
        provider_data={"mode": "development_fake"},
    )
