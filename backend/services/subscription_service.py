from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from models.subscription_model import Subscription, SubscriptionStatus
from models.tariffs_model import TariffPlan


logger = setup_logger(__name__)


async def get_subscription_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


async def get_active_subscription_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Optional[Subscription]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(
                [SubscriptionStatus.DEMO, SubscriptionStatus.ACTIVE]
            ),
            Subscription.current_period_start <= now,
            Subscription.current_period_end >= now,
        )
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


async def get_subscription_by_payment_id(
    session: AsyncSession,
    payment_id: UUID,
) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription).where(Subscription.payment_id == payment_id)
    )
    return result.scalar_one_or_none()


async def create_subscription(
    session: AsyncSession,
    user_id: UUID,
    tariff_id: UUID,
    *,
    payment_id: UUID | None = None,
) -> Subscription:
    tariff_result = await session.execute(
        select(TariffPlan).where(TariffPlan.id == tariff_id)
    )
    tariff = tariff_result.scalar_one_or_none()
    if tariff is None:
        raise ValueError("Тариф не найден")

    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user_id,
        tariff_id=tariff_id,
        payment_id=payment_id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        auto_renew=False,
        yookassa_payment_id=None,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def create_demo_subscription(
    session: AsyncSession,
    user_id: UUID,
    tariff_id: UUID,
    *,
    days: int = 7,
) -> Subscription:
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user_id,
        tariff_id=tariff_id,
        payment_id=None,
        status=SubscriptionStatus.DEMO,
        current_period_start=now,
        current_period_end=now + timedelta(days=days),
        auto_renew=False,
        yookassa_payment_id=None,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def deactivate_active_subscriptions(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(
                [SubscriptionStatus.DEMO, SubscriptionStatus.ACTIVE]
            ),
        )
    )
    for subscription in result.scalars().all():
        subscription.status = SubscriptionStatus.EXPIRED
        if subscription.current_period_end > now:
            subscription.current_period_end = now
        subscription.updated_at = now
    await session.flush()


async def cancel_subscription(
    session: AsyncSession,
    subscription: Subscription,
) -> Subscription:
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.auto_renew = False
    subscription.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return subscription
