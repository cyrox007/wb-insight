import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from models.sync_job_model import SyncJob
from services.marketplace_access_service import get_allowed_wb_tokens
from services.sync_job_service import get_next_jobs, mark_jobs_processing
from services.user_sync_state_service import get_state
from sync.router import call_wb_api


logger = setup_logger(__name__, 'processor.log')


async def worker_loop(session: AsyncSession):
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
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.is_active = False
            job.finished_at = datetime.now(timezone.utc)

    await session.commit()


async def process_job(session: AsyncSession, job: SyncJob):
    tokens = await get_allowed_wb_tokens(session, job.user_id)
    if not tokens:
        logger.warning(
            "[JOB %s] No tariff-allowed WB tokens for user %s",
            job.id,
            job.user_id,
        )
        raise RuntimeError("Нет доступных кабинетов Wildberries для синхронизации")

    # Current schema still keeps one state per user + entity. Until the
    # account-scoped migration lands, process only the tariff-allowed accounts.
    for token in tokens:
        state = await get_state(session, job.user_id, job.entity)
        now = datetime.now(timezone.utc)
        state.last_sync_at = now

        try:
            await call_wb_api(session=session, token=token, job=job)
            state.last_success_at = now
            state.last_error = None
        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "[JOB %s] WB API error for token %s: %s",
                job.id,
                token.id,
                error_msg,
            )
            state.last_error = error_msg

            if (
                "401" in error_msg
                or "403" in error_msg
                or "Unauthorized" in error_msg
            ):
                token.is_active = False
                state.last_error = (
                    "Ошибка авторизации: токен недействителен или истёк. "
                    "Обновите подключение Wildberries в настройках."
                )
            raise


@celery_app.task(name="tasks.processors.job_processor.run")
def run_worker():
    asyncio.run(_run_worker())


async def _run_worker():
    session = await get_session()
    try:
        await worker_loop(session)
    finally:
        await session.close()
