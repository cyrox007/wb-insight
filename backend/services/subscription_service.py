from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.subscription_model import Subscription, SubscriptionStatus
from models.tariffs_model import TariffPlan


async def create_subscription(
    session: AsyncSession,
    user_id: UUID,
    tariff_id: UUID,
    *,
    payment_id: UUID | None = None,
) -> Subscription:
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user_id,
        tariff_id=tariff_id,
        payment_id=payment_id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        yookassa_payment_id=None,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def create_demo_subscription(
    db: AsyncSession,
    user_id: UUID,
) -> Subscription:
    result = await db.execute(
        select(TariffPlan).where(TariffPlan.code == "DEMO")
    )
    demo_tariff = result.scalar_one()
    now = datetime.now(timezone.utc)

    subscription = Subscription(
        user_id=user_id,
        tariff_id=demo_tariff.id,
        payment_id=None,
        status=SubscriptionStatus.DEMO,
        current_period_start=now,
        current_period_end=now + timedelta(days=7),
        yookassa_payment_id=None,
    )
    db.add(subscription)
    await db.flush()
    return subscription


async def get_active_subscription(
    session: AsyncSession,
    user_id: UUID,
) -> Optional[Subscription]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.DEMO,
            ]),
            Subscription.current_period_end > now,
        )
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_active_subscription_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Optional[Subscription]:
    """Explicit alias used by newer code; legacy callers use get_active_subscription."""
    return await get_active_subscription(session, user_id)


async def get_subscription_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_subscription_by_payment_id(
    session: AsyncSession,
    payment_id: UUID,
) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription).where(Subscription.payment_id == payment_id)
    )
    return result.scalar_one_or_none()


async def activate_subscription(
    session: AsyncSession,
    subscription_id: UUID,
) -> bool:
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return False

    now = datetime.now(timezone.utc)
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    subscription.status = SubscriptionStatus.ACTIVE
    await session.flush()
    return True


# Backward-compatible alias for existing callers while the typo is retired.
activate_subcription = activate_subscription


async def cancel_subscription(
    session: AsyncSession,
    subscription: Subscription,
) -> bool:
    if subscription.status not in {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.DEMO,
    }:
        return False
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return True


async def cantelled_subscription(
    session: AsyncSession,
    subscription_or_id,
) -> bool:
    """Backward-compatible wrapper for the legacy misspelled function."""
    if isinstance(subscription_or_id, Subscription):
        return await cancel_subscription(session, subscription_or_id)

    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_or_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return False
    return await cancel_subscription(session, subscription)


async def deactivate_active_subscriptions(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    await session.execute(
        update(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.DEMO,
            ]),
        )
        .values(status=SubscriptionStatus.EXPIRED)
    )
    await session.flush()


async def get_user_subscription(
    db: AsyncSession,
    user_id: UUID,
) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
        .options(selectinload(Subscription.tariff))
    )
    return result.scalar_one_or_none()
