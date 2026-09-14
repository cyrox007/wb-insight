import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from models.sync_job_model import SyncJob
from models.tokens_model import Marketplace
from services.marketplace_access_service import get_allowed_wb_tokens
from services.sync_job_service import get_next_jobs, mark_jobs_processing
from services.token_services import get_token_by_id
from services.user_sync_state_service import get_state
from sync.router import call_wb_api


logger = setup_logger(__name__, "processor.log")


async def worker_loop(session: AsyncSession) -> int:
    jobs = await get_next_jobs(session, limit=10)
    if not jobs:
        return 0

    await mark_jobs_processing(session, jobs)
    await session.commit()

    processed = 0
    for job in jobs:
        try:
            await process_job(session, job)
            job.status = "done"
            job.error = None
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.is_active = False
            job.finished_at = datetime.now(timezone.utc)
            processed += 1

    await session.commit()
    return processed


async def process_job(session: AsyncSession, job: SyncJob) -> None:
    """Process exactly the marketplace credential stored on the job."""
    token = await get_token_by_id(session, job.token_id)
    if token is None or token.user_id != job.user_id:
        raise RuntimeError("Кабинет синхронизации не найден")
    if token.marketplace != Marketplace.WILDBERRIES or not token.is_valid:
        raise RuntimeError("Кабинет Wildberries недоступен для синхронизации")

    allowed_tokens = await get_allowed_wb_tokens(session, job.user_id)
    if token.id not in {allowed.id for allowed in allowed_tokens}:
        raise RuntimeError("Кабинет Wildberries недоступен на текущем тарифе")

    state = await get_state(
        session=session,
        user_id=job.user_id,
        token_id=job.token_id,
        entity_code=job.entity,
    )

    attempt_at = datetime.now(timezone.utc)
    state.last_sync_at = attempt_at

    try:
        await call_wb_api(session=session, token=token, job=job)
        state.last_success_at = datetime.now(timezone.utc)
        state.last_error = None
    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "[JOB %s] WB API error user=%s token=%s entity=%s: %s",
            job.id,
            job.user_id,
            token.id,
            job.entity,
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
                "Ошибка авторизации: подключение недействительно или истекло. "
                "Обновите кабинет Wildberries в настройках."
            )
        raise


@celery_app.task(name="tasks.processors.job_processor.run")
def run_worker():
    asyncio.run(_run_worker())


async def _run_worker() -> None:
    session = await get_session()
    try:
        await worker_loop(session)
    except Exception:
        await session.rollback()
        logger.exception("Sync job worker failed")
        raise
    finally:
        await session.close()
