from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription_model import Subscription, SubscriptionStatus
from models.sync_job_model import SyncJob
from models.user_sync_state_model import UserSyncState
from models.users_model import User
from models.tokens_model import APIToken, Marketplace

from services.tariff_service import get_tariff_limits_by_id
from services.token_services import get_tokens_by_user_id
from tasks.processor import process_job


async def schedule_all_users(session: AsyncSession):
    result = await session.execute(select(User))
    users = result.scalars().all()

    for user in users:
        # получаем лимиты тарифа
        user_subscription = (await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )).scalar_one_or_none()

        if not user_subscription:
            continue

        lim_res = await get_tariff_limits_by_id(session, user_subscription.tariff_id)
        limits: dict[str, int] = {cast(str, row.limit_type): cast(int, row.limit_value) for row in lim_res}
        
        tokens = await get_tokens_by_user_id(session, user.id)

        # 🔥 лимит WB аккаунтов
        wb_limit = limits.get("wb_accounts", 1)

        tokens = [
            t for t in tokens
            if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
        ][:wb_limit]

        if not tokens:
            continue

        for token in tokens:
            await create_job_if_needed(
                session,
                user_id=user.id,
                token_id=cast(UUID, token.id),
                entity="stocks",
                limits=limits
            )

            await create_job_if_needed(
                session,
                user_id=user.id,
                token_id=cast(UUID, token.id),
                entity="realization",
                limits=limits
            )

async def create_job_if_needed(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    entity: str,
    limits: dict
):
    now = datetime.utcnow()

    # 1. берём состояние синка
    state = await session.execute(
        select(UserSyncState).where(
            UserSyncState.user_id == user_id,
            UserSyncState.token_id == token_id,
            UserSyncState.entity == entity
        )
    )
    state = state.scalar_one_or_none()

    # 2. проверяем частоту (из тарифа)
    sync_hours = limits.get("sync_frequency_hours", 1)  # дефолт 1 час
    interval = timedelta(hours=sync_hours)

    if state and state.last_sync_at:
        if now - state.last_sync_at < interval:
            return  # ❌ ещё рано

    # 3. формируем payload
    payload = build_payload(entity, state, limits)

    # 4. создаём job
    job = SyncJob(
        user_id=user_id,
        token_id=token_id,
        entity=entity,
        payload=payload,
        status="pending"
    )

    session.add(job)
    await session.flush()

    # 5. отправляем в Celery
    process_job.delay(str(job.id))

    await session.commit()

def build_payload(entity, state, limits):
    now = datetime.utcnow()

    retention_days = limits.get("retention_days", 30)
    max_lookback = timedelta(days=retention_days)

    if entity == "stocks":
        if not state or not state.last_sync_at:
            return {
                "dateFrom": (now - max_lookback).isoformat()
            }

        return {
            "dateFrom": max(
                state.last_sync_at - timedelta(minutes=5),
                now - max_lookback
            ).isoformat()
        }

    elif entity == "realization":
        if not state or not state.last_sync_at:
            return {
                "dateFrom": (now - max_lookback).date().isoformat(),
                "dateTo": now.date().isoformat()
            }

        return {
            "dateFrom": max(
                state.last_sync_at.date(),
                (now - max_lookback).date()
            ).isoformat(),
            "dateTo": now.date().isoformat()
        }