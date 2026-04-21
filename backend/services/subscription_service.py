from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription_model import Subscription, SubscriptionStatus
from models.tariffs_model import TariffPlan


async def create_subscription(
    session: AsyncSession,
    user_id: UUID,
    tariff_id: UUID
) -> Subscription:
    now = datetime.now(timezone.utc)

    sub = Subscription(
        user_id=user_id,
        tariff_id=tariff_id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        yookassa_payment_id=None
    )

    session.add(sub)
    await session.flush()

    return sub

async def create_demo_subscription(
    db: AsyncSession,
    user_id: UUID,
) -> Subscription:
    # найти демо тариф
    result = await db.execute(
        select(TariffPlan).where(TariffPlan.code == "DEMO")
    )
    demo_tariff = result.scalar_one()

    now = datetime.utcnow()

    subscription = Subscription(
        user_id=user_id,
        tariff_id=demo_tariff.id,
        status=SubscriptionStatus.DEMO,
        start_date=now,
        end_date=now + timedelta(days=7),  # например 7 дней
        auto_renew=False,
    )

    db.add(subscription)
    await db.flush()

    return subscription

async def get_active_subscription(
    session: AsyncSession,
    user_id: UUID
) -> Optional[Subscription]:

    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.current_period_end > now
        )
    )

    return result.scalar_one_or_none()


async def activate_subcription(session: AsyncSession, subscription_id: UUID) -> bool:
    now = datetime.now(timezone.utc)

    res = await session.execute(
        select(Subscription).where(
            Subscription.id == subscription_id
        )
    )

    sub = res.scalar_one_or_none()

    if sub is None:
        return False
    
    # sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.status = SubscriptionStatus.ACTIVE

    return True

async def cantelled_subscription(session: AsyncSession, subscription_id: UUID) -> bool:
    result = await session.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )

    sub = result.scalar_one_or_none()

    if sub is None:
        return False
    
    sub.status = SubscriptionStatus.CANCELLED
    await session.flush()
    return True

async def deactivate_active_subscriptions(session: AsyncSession, user_id: UUID):
    await session.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .values(status=SubscriptionStatus.EXPIRED)
    )