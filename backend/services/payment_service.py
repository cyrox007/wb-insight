from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payments_model import Payment, PaymentStatus, PaymentProvider
from models.subscription_model import SubscriptionStatus
#from services.subscription_service import activate_subscription


# 🟢 создать платеж
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
        status=PaymentStatus.PENDING.value,
        provider=provider,
        updated_at=datetime.utcnow()
    )

    db.add(payment)
    await db.flush()

    return payment


# 🟢 получить платеж
async def get_payment(
    db: AsyncSession,
    payment_id: UUID,
) -> Payment | None:

    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    return result.scalar_one_or_none()


# 🟢 успешная оплата (главная функция)
async def mark_payment_succeeded(
    db: AsyncSession,
    payment: Payment,
    external_payment_id: str | None = None,
    provider_data: dict | None = None,
) -> None:

    # ❗ защита от повторной обработки (idempotency)
    if payment.status == PaymentStatus.SUCCEEDED:
        return

    payment.status = PaymentStatus.SUCCEEDED
    payment.external_payment_id = external_payment_id
    payment.provider_data = provider_data
    payment.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return


# 🔴 неуспешная оплата
async def mark_payment_failed(
    db: AsyncSession,
    payment: Payment,
    metadata: dict | None = None,
) -> None:

    if payment.status == PaymentStatus.SUCCEEDED:
        return

    payment.status = PaymentStatus.FAILED
    payment.metadata = metadata
    payment.updated_at = datetime.now(timezone.utc)


# 🧪 fake оплата (для разработки)
async def fake_pay(
    db: AsyncSession,
    payment_id: UUID,
    user_id: UUID,
) -> Payment:

    payment = await get_payment(db, payment_id)

    if not payment:
        raise ValueError("Payment not found")

    if payment.user_id != user_id:
        raise PermissionError("Not your payment")

    await mark_payment_succeeded(db, payment)

    return payment