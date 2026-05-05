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
    user_tokens = await get_tokens_by_user_id(session, job.user_id)

    tokens = [
        t for t in user_tokens
        if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
    ]

    if not tokens:
        logger.warning(f"[JOB {job.id}] No valid tokens for user {job.user_id}")
        raise Exception("Нет действительных токенов для синхронизации")

    for token in tokens:
        state = await get_state(session, job.user_id, job.entity)

        now = datetime.now(timezone.utc)
        state.last_sync_at = now
        try:
            await call_wb_api(session=session, token=token, job=job)
            state.last_success_at = now
            state.last_error = None

            # Если задача успешно выполнена - помечаем её как выполненную
            job.status = "done"
            job.finished_at = now
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[JOB {job.id}] Произошла ошибка во время вызова API: {error_msg}")
            state.last_error = error_msg

            # Специальная обработка ошибок авторизации (401/403)
            if "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg:
                logger.warning(f"[JOB {job.id}] Токен недействителен (401/403). Помечаем токен как неактивный.")
                # Помечаем токен как неактивный, чтобы не пытаться использовать его снова
                token.is_active = False
                # Также можно добавить специальное сообщение об ошибке
                state.last_error = f"Ошибка авторизации: токен недействителен или истек срок действия. Пожалуйста, обновите токен в настройках."

            # Пробрасываем ошибку выше, чтобы job получил статус failed
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