""" from celery_app import celery_app
import asyncio

from core.logger import setup_logger
from database_celery import get_session
from services.sync import schedule_all_users

logger = setup_logger(__name__, 'sheduler.log')

async def _schedule():
    session = await get_session()
    logger.info(f"Создали сессию: {session}")
    try:
        await schedule_all_users(session)
        await session.commit()
        logger.info(f"Комит выполнен")
    except Exception as e:
        await session.rollback()
        logger.error(f"Возникла ошибка: {e}")
        raise
    finally:
        await session.close()

@celery_app.task(name="tasks.scheduler.schedule_sync", rate_limit="5/m")
def schedule_sync():
    logger.info("Начинаем планировщик")
    asyncio.run(_schedule())
 """

import asyncio
from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select, exists, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.logger import setup_logger
from core.database_celery import get_session

from models.tariffs_model import TariffPlan
from models.user_sync_state_model import UserSyncState
from models.users_model import User
from models.subscription_model import Subscription, SubscriptionStatus
from models.tokens_model import APIToken, Marketplace
from services.sync_job_service import create_sync_job
from services.user_sync_state_service import get_states_batch

logger = setup_logger(__name__, 'sheduler.log')

BATCH_SIZE = 50

def filter_user_tokens(user: User) -> list[APIToken]:
    limits = {
        l.limit_type: l.limit_value
        for l in user.subscription.tariff.limits
    }

    wb_limit = limits.get("wb_accounts", 1)

    tokens = [
        t for t in user.api_tokens
        if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
    ]

    return tokens[:wb_limit]

async def function_sheduler(session: AsyncSession):
    last_created_at = None
    last_id = None

    while True:
        states = await get_states_batch(
            session=session,
            last_created_at=last_created_at,
            last_id=last_id,
            limit=BATCH_SIZE
        )

        if not states:
            break

        for state in states:
            user = state.user

            if not user.subscription:
                continue

            tokens = filter_user_tokens(user)
            
            if not tokens:
                continue

            await create_sync_job(
                session=session,
                user_id=user.id,
                entity=state.entity
            )

        last_created_at = states[-1].created_at
        last_id = states[-1].id
        await session.commit()

async def _shedule():
    session = await get_session()

    try:
        await function_sheduler(session)
    except Exception as e:
        logger.error(f"def[_sheduler] error: {e}")
        await session.rollback()
    finally:
        await session.close()

@celery_app.task(name='tasks.schedulers.state_scheduler.schedule_sync')
def schedule_sync():
    asyncio.run(_shedule())