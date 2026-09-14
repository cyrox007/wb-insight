import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from models.subscription_model import SubscriptionStatus
from services.marketplace_access_service import get_allowed_wb_tokens
from services.payload_builder import build_payload_for_entity
from services.sync_job_service import create_sync_job
from services.user_sync_state_service import get_states_batch


logger = setup_logger(__name__, "scheduler.log")
BATCH_SIZE = 100


def _current_subscription(user, now: datetime):
    candidates = [
        subscription
        for subscription in user.subscriptions
        if subscription.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.DEMO,
        }
        and subscription.current_period_start <= now < subscription.current_period_end
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda subscription: subscription.current_period_end)


def _sync_interval(subscription) -> timedelta | None:
    sync_limit = next(
        (
            limit
            for limit in subscription.tariff.limits
            if limit.limit_type == "sync_frequency_hours"
        ),
        None,
    )
    if sync_limit is None:
        return None

    hours = max(1, int(sync_limit.limit_value))
    return timedelta(hours=hours)


async def function_sheduler(session: AsyncSession) -> int:
    """Schedule all due account-scoped states."""
    logger.info("[SCHEDULER] start")
    last_created_at = None
    last_id: UUID | None = None
    jobs_created = 0
    allowed_token_cache: dict[UUID, set[UUID]] = {}

    while True:
        states = await get_states_batch(
            session=session,
            last_created_at=last_created_at,
            last_id=last_id,
            limit=BATCH_SIZE,
        )
        if not states:
            break

        for state in states:
            now = datetime.now(timezone.utc)
            user = state.user
            subscription = _current_subscription(user, now)
            if subscription is None or subscription.tariff is None:
                continue

            interval = _sync_interval(subscription)
            if interval is None:
                continue

            if state.last_sync_at is not None and now - state.last_sync_at < interval:
                continue

            allowed_token_ids = allowed_token_cache.get(user.id)
            if allowed_token_ids is None:
                allowed_tokens = await get_allowed_wb_tokens(session, user.id)
                allowed_token_ids = {token.id for token in allowed_tokens}
                allowed_token_cache[user.id] = allowed_token_ids

            if state.token_id not in allowed_token_ids:
                continue

            payload = build_payload_for_entity(
                state.entity,
                state.last_success_at,
                state.source_cursor,
            )
            created = await create_sync_job(
                session=session,
                user_id=user.id,
                token_id=state.token_id,
                entity=state.entity,
                payload=payload,
            )
            jobs_created += int(created)

        last_created_at = states[-1].created_at
        last_id = states[-1].id
        if len(states) < BATCH_SIZE:
            break

    await session.commit()
    logger.info("[SCHEDULER] finished jobs_created=%s", jobs_created)
    return jobs_created


async def _schedule() -> None:
    session = await get_session()
    try:
        await function_sheduler(session)
    except Exception:
        await session.rollback()
        logger.exception("State scheduler failed")
        raise
    finally:
        await session.close()


@celery_app.task(name="tasks.schedulers.state_scheduler.schedule_sync")
def schedule_sync():
    asyncio.run(_schedule())
