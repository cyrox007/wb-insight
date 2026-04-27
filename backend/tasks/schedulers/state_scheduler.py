import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.logger import setup_logger
from core.database_celery import get_session

from models.users_model import User
from models.subscription_model import SubscriptionStatus
from models.tokens_model import APIToken, Marketplace
from services.sync_job_service import create_sync_job
from services.user_sync_state_service import get_states_batch

logger = setup_logger(__name__, 'sheduler.log')

BATCH_SIZE = 50

_scheduler_state = {
    "last_created_at": None,
    "last_id": None
}

def filter_user_tokens(user: User) -> list[APIToken]:
    logger.debug(f"[TOKENS] user={user.id} start filtering")
    sub = next(
        (s for s in user.subscriptions if s.status == SubscriptionStatus.ACTIVE),
        None
    )

    if not sub:
        logger.debug(f"[TOKENS] user={user.id} no active subscription")
        return []
    
    limits = {
        l.limit_type: l.limit_value
        for l in sub.tariff.limits
    }

    wb_limit = limits.get("wb_accounts", 1)

    tokens = [
        t for t in user.api_tokens
        if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
    ]

    logger.debug(
        f"[TOKENS] user={user.id} total_valid={len(tokens)} limit={wb_limit}"
    )

    return tokens[:wb_limit]

async def function_sheduler(session: AsyncSession):
    logger.info("[SCHEDULER] start")

    #last_created_at = None
    #last_id = None

    last_created_at = _scheduler_state["last_created_at"]
    last_id = _scheduler_state["last_id"]

    #while True:
    logger.debug(
        f"[BATCH] request last_created_at={last_created_at} last_id={last_id}"
    )

    states = await get_states_batch(
        session=session,
        last_created_at=last_created_at,
        last_id=last_id,
        limit=BATCH_SIZE
    )

    logger.info(f"[BATCH] fetched states={len(states)}")

    if not states:
        logger.info("[SCHEDULER] no more states, exit")
        return
    
    jobs_created = 0
    users_processed = set()

    for state in states:
        user = state.user

        users_processed.add(user.id)

        logger.debug(
            f"[STATE] id={state.id} user={user.id} entity={state.entity}"
        )

        if not user.subscriptions:
            logger.debug(f"[SKIP] user={user.id} no subscriptions")
            continue

        now = datetime.now(timezone.utc)

        active_sub = next(
            (s for s in user.subscriptions if s.status == SubscriptionStatus.ACTIVE),
            None
        )

        if not active_sub:
            logger.debug(f"[SKIP] user={user.id} no active subscription")
            continue

        if not active_sub.tariff:
            logger.debug(f"[SKIP] user={user.id} no tariff")
            continue

        limits = active_sub.tariff.limits

        sync_limit = next(
            (l for l in limits if l.limit_type == "sync_frequency_hours"),
            None
        )

        if not sync_limit:
            logger.debug(f"[SKIP] user={user.id} no sync_frequency_hours limit")
            continue

        hours = int(sync_limit.limit_value)
        interval = timedelta(hours=hours)

        if state.last_sync_at:
            diff = now - state.last_sync_at
            
            logger.debug(
                f"[CHECK] user={user.id} entity={state.entity} "
                f"last_sync={state.last_sync_at} diff={diff} interval={interval}"
            )
            
            if diff < interval:
                logger.debug(f"[SKIP] cooldown not passed")
                continue

        tokens = filter_user_tokens(user)

        if not tokens:
            logger.debug(f"[SKIP] user={user.id} no valid tokens")
            continue

        logger.info(
            f"[JOB] create user={user.id} entity={state.entity}"
        )

        await create_sync_job(
            session=session,
            user_id=user.id,
            entity=state.entity,
            payload={
                "date_from": state.last_sync_at.isoformat() if state.last_sync_at else None,
                "date_to": datetime.now(timezone.utc).isoformat()
            }
        )

        jobs_created += 1

    #last_created_at = states[-1].created_at
    #last_id = states[-1].id

    # Сохраняем состояние для следующего запуска
    if states:
        _scheduler_state["last_created_at"] = states[-1].created_at
        _scheduler_state["last_id"] = states[-1].id

    logger.debug(
        f"[BATCH] next cursor created_at={last_created_at} id={last_id}"
    )

    await session.commit()
    logger.debug("[BATCH] committed")

    logger.info("[SCHEDULER] finished")

async def _shedule():
    logger.info("[TASK] schedule_sync start")

    session = await get_session()

    try:
        await function_sheduler(session)
    except Exception as e:
        logger.error(f"def[_sheduler] error: {e}", exc_info=True)
        await session.rollback()
    finally:
        await session.close()
        logger.info("[TASK] schedule_sync finished")

@celery_app.task(name='tasks.schedulers.state_scheduler.schedule_sync')
def schedule_sync():
    asyncio.run(_shedule())