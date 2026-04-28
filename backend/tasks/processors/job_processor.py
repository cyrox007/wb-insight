import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from models.sync_job_model import SyncJob
from models.tokens_model import Marketplace
from models.users_model import User
from services.sync_job_service import get_next_jobs, mark_jobs_processing
from services.token_services import get_tokens_by_user_id
from services.user_sync_state_service import get_state
from sync.router import call_wb_api

logger = setup_logger(__name__, 'processor.log')

async def worker_loop(session: AsyncSession):
    #while True:
    jobs = await get_next_jobs(session, limit=10)

    if not jobs:
        return

    await mark_jobs_processing(session, jobs)
    await session.commit()

    for job in jobs:
        try:
            await process_job(session, job)

            job.status = "done"
            job.is_active = False
            job.finished_at = datetime.now(timezone.utc)

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.is_active = False
            job.finished_at = datetime.now(timezone.utc)

    await session.commit()


async def process_job(session: AsyncSession, job: SyncJob):
    # user = await session.get(User, job.user_id)

    user_tokens = await get_tokens_by_user_id(session, job.user_id)

    tokens = [
        t for t in user_tokens
        if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
    ]

    if not tokens:
        return

    for token in tokens:
        state = await get_state(session, job.user_id, job.entity)

        now = datetime.now(timezone.utc)

        try:
            await call_wb_api(session=session, token=token, job=job)
            state.last_success_at = now
        except Exception as e:
            logger.error(f"Произошла ошибка по время вызова API: {e}")
            state.last_error = str(e)
        finally:
            state.last_sync_at = now
        

@celery_app.task(name="tasks.processors.job_processor.run")
def run_worker():
    asyncio.run(_run_worker())


async def _run_worker():
    session = await get_session()

    try:
        await worker_loop(session)
    finally:
        await session.close()