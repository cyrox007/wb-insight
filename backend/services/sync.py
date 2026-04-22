from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.subscription_model import Subscription, SubscriptionStatus
from models.sync_job_model import SyncJob
from models.user_sync_state_model import UserSyncState
from models.users_model import User
from models.tokens_model import APIToken, Marketplace

from core.logger import setup_logger
from services.tariff_service import get_tariff_limits_by_id
from services.token_services import get_tokens_by_user_id
from tasks.processor import process_job

REALIZATION_INTERVAL = timedelta(hours=24)
DEFAULT_INTERVAL = timedelta(minutes=10)

logger = setup_logger(__name__, 'sheduler.log')

async def schedule_all_users(session: AsyncSession):
    result = await session.execute(select(User))
    users = result.scalars().all()
    logger.info(f"Получили пользователей: {len(users)}")
    
    for user in users:
        # получаем лимиты тарифа
        user_subscription = (await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )).scalar_one_or_none()

        if not user_subscription:
            logger.warning("Подписок пользователя не получили")
            continue

        logger.info(f"Подписка пользователя: {user_subscription.id}, на тариф ID: {user_subscription.tariff_id}")
        
        lim_res = await get_tariff_limits_by_id(session, user_subscription.tariff_id)
        logger.info(f"Получено лимитов: {len(lim_res)}")
        limits: dict[str, int] = {cast(str, row.limit_type): cast(int, row.limit_value) for row in lim_res}
        logger.info(f"{limits}")


        tokens = await get_tokens_by_user_id(session, user.id)

        # 🔥 лимит WB аккаунтов
        wb_limit = limits.get("wb_accounts", 1)
        logger.info(f"Полученный лимит: {wb_limit}")
        
        tokens = [
            t for t in tokens
            if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
        ][:wb_limit]

        logger.info(f"Кол-во токенов: {len(tokens)}")
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
    now = datetime.now(timezone.utc)
    stmt = insert(UserSyncState).values(
        user_id=user_id,
        token_id=token_id,
        entity=entity,
        last_sync_at=None
    ).on_conflict_do_nothing(
        index_elements=["user_id", "token_id", "entity"]
    )

    await session.execute(stmt)
    await session.flush()
    
    # 1. берём состояние синка
    state = await session.execute(
        select(UserSyncState).where(
            UserSyncState.user_id == user_id,
            UserSyncState.token_id == token_id,
            UserSyncState.entity == entity
        )
    )
    state = state.scalar_one()

    # 2. проверяем частоту (из тарифа)
    sync_hours = limits.get("sync_frequency_hours", 1)  # дефолт 1 час
    interval = timedelta(hours=sync_hours)
    
    logger.info(f"[CHECK] entity={entity}")
    logger.info(f"[CHECK] now={now}")
    logger.info(f"[CHECK] interval={interval}")
    logger.info(f"[CHECK] last_sync_at={state.last_sync_at}")
    logger.info(f"[CHECK] last_error={state.last_error}")

    # 🚨 1. если была ошибка rate_limit — не долбим API
    if state.last_sync_at is None and state.last_error == "rate_limit":
        logger.info("[SKIP] предыдущий запуск упал по rate_limit → ждём")
        return

    # 2. обычная проверка интервала
    if state.last_sync_at:
        diff = now - state.last_sync_at
        logger.info(f"[CHECK] diff={diff}")

        if diff < interval:
            logger.info(f"[SKIP] diff < interval → {diff} < {interval}")
            return
        else:
            logger.info(f"[RUN] diff >= interval → {diff} >= {interval}")

    # 3. первичная синхронизация
    else:
        logger.info("[RUN] первичная синхронизация (нет last_sync_at)")

    logger.info("Видимо еще не рано делать синхронизацию")
    existing_job = await session.execute(
        select(SyncJob).where(
            SyncJob.user_id == user_id,
            SyncJob.token_id == token_id,
            SyncJob.entity == entity,
            SyncJob.status.in_(["pending", "processing", "failed"])
        )
    )

    if existing_job.scalar_one_or_none():
        logger.info("Уже есть активная задача — пропускаем")
        return
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
    now = datetime.now(timezone.utc)

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