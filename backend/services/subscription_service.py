from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tariffs import Subscription


async def create_subscription(
    session: AsyncSession,
    user_id: UUID,
    tariff_id: UUID
) -> Subscription:
    now = datetime.now(timezone.utc)

    sub = Subscription(
        user_id=user_id,
        tariff_id=tariff_id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=7),
        yookassa_payment_id=None
    )

    session.add(sub)
    await session.flush()

    return sub

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