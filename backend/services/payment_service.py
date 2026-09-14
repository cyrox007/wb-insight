from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payments_model import Payment, PaymentProvider, PaymentStatus


async def create_payment(
    db: AsyncSession,
    user_id: UUID,
    tariff_id: UUID,
    amount,
    provider: PaymentProvider = PaymentProvider.FAKE,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=amount,
        status=PaymentStatus.PENDING,
        provider=provider,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.flush()
    return payment


async def get_payment(
    db: AsyncSession,
    payment_id: UUID,
    user_id: UUID | None = None,
) -> Payment | None:
    query = select(Payment).where(Payment.id == payment_id)
    if user_id is not None:
        query = query.where(Payment.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def mark_payment_succeeded(
    db: AsyncSession,
    payment: Payment,
    external_payment_id: str | None = None,
    provider_data: dict | None = None,
) -> None:
    if payment.status == PaymentStatus.SUCCEEDED:
        return
    if payment.status != PaymentStatus.PENDING:
        raise ValueError(f"Cannot succeed payment in status {payment.status}")

    payment.status = PaymentStatus.SUCCEEDED
    payment.external_payment_id = external_payment_id
    payment.provider_data = provider_data
    payment.updated_at = datetime.now(timezone.utc)
    await db.flush()


async def mark_payment_failed(
    db: AsyncSession,
    payment: Payment,
    provider_data: dict | None = None,
) -> None:
    if payment.status == PaymentStatus.SUCCEEDED:
        return

    payment.status = PaymentStatus.FAILED
    payment.provider_data = provider_data
    payment.updated_at = datetime.now(timezone.utc)
    await db.flush()


async def fake_pay(
    db: AsyncSession,
    payment_id: UUID,
    user_id: UUID,
) -> Payment:
    payment = await get_payment(db, payment_id, user_id=user_id)
    if not payment:
        raise ValueError("Payment not found")

    if payment.provider != PaymentProvider.FAKE:
        raise ValueError("Payment is not a fake-provider payment")

    await mark_payment_succeeded(db, payment)
    return payment
