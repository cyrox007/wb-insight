import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from integrations.wildberries.client import (
    WBAPIError,
    WBAuthError,
    WBRateLimitError,
)
from models.sync_job_model import SyncJob
from models.tokens_model import Marketplace
from services.marketplace_access_service import get_allowed_wb_tokens
from services.sync_job_service import (
    claim_next_job,
    complete_job,
    fail_job,
    recover_stale_jobs,
    retry_job,
)
from services.token_services import get_token_by_id
from services.user_sync_state_service import get_state
from settings import config
from sync.router import call_wb_api


logger = setup_logger(__name__, "processor.log")


class PermanentSyncJobError(RuntimeError):
    """The same job payload/account should not be retried unchanged."""


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (WBAuthError, PermanentSyncJobError, ValueError)):
        return False
    if isinstance(exc, WBRateLimitError):
        return True
    if isinstance(exc, WBAPIError):
        return exc.status_code is None or exc.status_code >= 500
    return True


async def worker_loop(session: AsyncSession, limit: int = 10) -> int:
    """Claim jobs just-in-time and recover abandoned processing leases."""
    requeued, stale_failed = await recover_stale_jobs(session)
    if requeued or stale_failed:
        logger.warning(
            "Recovered stale sync jobs requeued=%s failed=%s",
            requeued,
            stale_failed,
        )
    await session.commit()

    processed = 0
    for _ in range(limit):
        job = await claim_next_job(session)
        if job is None:
            await session.commit()
            break

        job_id = job.id
        await session.commit()

        try:
            await process_job(session, job)
            await complete_job(session, job)
            await session.commit()
        except Exception as exc:
            # A persistence error can leave the current SQLAlchemy transaction
            # unusable. Roll it back before recording durable retry/failure state.
            await session.rollback()
            fresh_job = await session.get(SyncJob, job_id)
            if fresh_job is None:
                logger.error("Claimed sync job disappeared id=%s", job_id)
                continue

            await _record_failure(session, fresh_job, exc)
            await session.commit()
        finally:
            processed += 1

    return processed


async def process_job(session: AsyncSession, job: SyncJob) -> None:
    """Process exactly the marketplace credential stored on the job."""
    token = await get_token_by_id(session, job.token_id)
    if token is None or token.user_id != job.user_id:
        raise PermanentSyncJobError("Кабинет синхронизации не найден")
    if token.marketplace != Marketplace.WILDBERRIES or not token.is_valid:
        raise PermanentSyncJobError(
            "Кабинет Wildberries недоступен для синхронизации"
        )

    allowed_tokens = await get_allowed_wb_tokens(session, job.user_id)
    if token.id not in {allowed.id for allowed in allowed_tokens}:
        raise PermanentSyncJobError(
            "Кабинет Wildberries недоступен на текущем тарифе"
        )

    state = await get_state(
        session=session,
        user_id=job.user_id,
        token_id=job.token_id,
        entity_code=job.entity,
    )
    state.last_sync_at = datetime.now(timezone.utc)

    try:
        await call_wb_api(session=session, token=token, job=job)
    except WBAuthError:
        # Keep direct process_job semantics explicit. The worker rolls this
        # transaction back on failure and records the same terminal state again
        # durably via _record_failure.
        token.is_active = False
        state.last_error = (
            "Ошибка авторизации: подключение недействительно или истекло. "
            "Обновите кабинет Wildberries в настройках."
        )
        raise

    state.last_success_at = datetime.now(timezone.utc)
    state.last_error = None


async def _record_failure(
    session: AsyncSession,
    job: SyncJob,
    exc: Exception,
) -> None:
    now = datetime.now(timezone.utc)
    error_text = str(exc)[:1000] or type(exc).__name__

    try:
        state = await get_state(
            session=session,
            user_id=job.user_id,
            token_id=job.token_id,
            entity_code=job.entity,
        )
        state.last_sync_at = now
        state.last_error = error_text
    except Exception:
        state = None
        logger.exception("Unable to update sync state after job failure id=%s", job.id)

    if isinstance(exc, WBAuthError):
        token = await get_token_by_id(session, job.token_id)
        if token is not None:
            token.is_active = False
        if state is not None:
            state.last_error = (
                "Ошибка авторизации: подключение недействительно или истекло. "
                "Обновите кабинет Wildberries в настройках."
            )
        await fail_job(session, job, error_text, now=now)
        logger.warning(
            "[JOB %s] WB authorization rejected user=%s token=%s entity=%s status=%s",
            job.id,
            job.user_id,
            job.token_id,
            job.entity,
            exc.status_code,
        )
        return

    if _is_retryable(exc) and job.attempt_count < config.SYNC_JOB_MAX_ATTEMPTS:
        await retry_job(session, job, error_text, now=now)
        logger.warning(
            "[JOB %s] scheduled retry attempt=%s/%s entity=%s error=%s",
            job.id,
            job.attempt_count,
            config.SYNC_JOB_MAX_ATTEMPTS,
            job.entity,
            type(exc).__name__,
        )
        return

    await fail_job(session, job, error_text, now=now)
    logger.warning(
        "[JOB %s] failed permanently attempt=%s/%s entity=%s error=%s",
        job.id,
        job.attempt_count,
        config.SYNC_JOB_MAX_ATTEMPTS,
        job.entity,
        type(exc).__name__,
    )


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
