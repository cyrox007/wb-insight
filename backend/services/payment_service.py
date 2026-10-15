from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.operation_context import get_operation_context
from integrations.sber.client import SberOrderStatus
from models.payments_model import (
    Payment,
    PaymentEvent,
    PaymentProvider,
    PaymentStatus,
)
from models.users_model import User
from services.operation_log_service import persist_current_operation_event
from services.subscription_service import (
    create_subscription,
    deactivate_active_subscriptions,
    get_subscription_by_payment_id,
)


def _payment_event_level(event_type: str) -> tuple[str, str]:
    normalized = str(event_type or "").lower()
    if any(fragment in normalized for fragment in ("error", "failed", "failure")):
        return "failed", "error"
    if any(fragment in normalized for fragment in ("skipped", "cancel", "declined")):
        return "warning", "warning"
    return "success", "info"


async def _trace_payment_operation(
    payment: Payment,
    *,
    step: str,
    status: str,
    severity: str = "info",
    request_id: str | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    message: str | None = None,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
) -> None:
    """Пишет диагностический шаг независимо от транзакции платежа."""
    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        operation_id=payment.id,
        domain="payment",
        operation="tariff_payment",
        step=step,
        status=status,
        severity=severity,
        user_id=payment.user_id,
        subject_type="payment",
        subject_id=payment.id,
        provider=payment.provider.value,
        request_id=request_id,
        duration_ms=duration_ms,
        error_code=error_code,
        message=message,
        input_data=input_data or {},
        output_data=output_data or {},
    )


async def _trace_payment_created(
    session: AsyncSession,
    payment: Payment,
    *,
    reused: bool = False,
) -> None:
    await _trace_payment_operation(
        payment,
        step="idempotency_reused" if reused else "payment_created",
        status="info" if reused else "started",
        message=(
            "Повторный запрос использовал ранее созданную платёжную попытку"
            if reused
            else "Создана платёжная попытка по тарифу"
        ),
        input_data={
            "tariff_id": payment.tariff_id,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "mode": payment.mode,
        },
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
    await _trace_payment_created(session, payment)
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
        await _trace_payment_created(session, existing, reused=True)
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
        await _trace_payment_created(session, payment)
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
        await _trace_payment_created(session, existing, reused=True)
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


async def is_payment_user_active(
    session: AsyncSession,
    user_id: UUID,
) -> bool:
    """Блокирует состояние аккаунта на время решения об активации подписки."""
    result = await session.execute(
        select(User.is_active)
        .where(User.id == user_id)
        .with_for_update()
    )
    return bool(result.scalar_one_or_none())


async def record_payment_event(
    session: AsyncSession,
    *,
    payment_id: UUID,
    event_type: str,
    provider_status: str | None = None,
    provider_data: dict[str, Any] | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    input_data: dict[str, Any] | None = None,
) -> PaymentEvent:
    event = PaymentEvent(
        payment_id=payment_id,
        event_type=event_type,
        provider_status=provider_status,
        provider_data=provider_data,
    )
    session.add(event)
    await session.flush()

    payment = await session.get(Payment, payment_id)
    if payment is not None:
        event_status, severity = _payment_event_level(event_type)
        await _trace_payment_operation(
            payment,
            step=event_type,
            status=event_status,
            severity=severity,
            request_id=request_id,
            duration_ms=duration_ms,
            error_code=error_code,
            message=f"Платёжный шаг: {event_type}",
            input_data=input_data or {},
            output_data={
                "provider_status": provider_status,
                "provider_data": provider_data or {},
            },
        )
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
    await _trace_payment_operation(
        payment,
        step="payment_succeeded",
        status="success",
        message="Провайдер подтвердил успешную оплату",
        output_data=provider_data or {},
    )
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
    await _trace_payment_operation(
        payment,
        step="payment_failed",
        status="failed",
        severity="error",
        error_code="PAYMENT_FAILED",
        message="Платёж завершён с ошибкой",
        output_data=provider_data or {},
    )
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
    """Применяет подтверждённый банком статус и не дублирует подписку."""

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
        await _trace_payment_operation(
            payment,
            step="bank_confirmed_paid",
            status="success",
            message="Банк подтвердил оплату",
            output_data=safe_data,
        )
        if existing_subscription is None:
            if await is_payment_user_active(session, payment.user_id):
                await deactivate_active_subscriptions(session, payment.user_id)
                existing_subscription = await create_subscription(
                    session,
                    payment.user_id,
                    payment.tariff_id,
                    payment_id=payment.id,
                )
                await record_payment_event(
                    session,
                    payment_id=payment.id,
                    event_type="subscription_activated",
                    provider_status=normalized,
                    provider_data={"subscription_id": str(existing_subscription.id)},
                )
            else:
                # Банк может подтвердить деньги уже после отключения аккаунта.
                # Платёж остаётся успешным, но доступ автоматически не выдаётся.
                await record_payment_event(
                    session,
                    payment_id=payment.id,
                    event_type="subscription_activation_skipped",
                    provider_status=normalized,
                    provider_data={"reason": "inactive_account"},
                )
    elif status.order_status == 6:
        payment.status = PaymentStatus.FAILED
        await record_payment_event(
            session,
            payment_id=payment.id,
            event_type="bank_payment_failed",
            provider_status=normalized,
            provider_data=safe_data,
        )
    elif status.order_status in {3, 4}:
        payment.status = PaymentStatus.CANCELLED
        await record_payment_event(
            session,
            payment_id=payment.id,
            event_type="bank_payment_cancelled",
            provider_status=normalized,
            provider_data=safe_data,
        )

    await session.flush()
    return payment, existing_subscription


async def fake_pay(session: AsyncSession, payment_id: UUID) -> Payment:
    payment = await get_payment(session, payment_id)
    if payment is None:
        raise ValueError("Платёж не найден")
    if payment.provider != PaymentProvider.FAKE:
        raise ValueError("Этот платёж нельзя подтвердить fake-провайдером")
    payment = await mark_payment_succeeded(
        session,
        payment,
        provider_data={"mode": "development_fake"},
    )
    await record_payment_event(
        session,
        payment_id=payment.id,
        event_type="fake_payment_confirmed",
        provider_status="development_fake",
        provider_data={"mode": "development_fake"},
    )
    return payment
