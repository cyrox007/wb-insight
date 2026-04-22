from datetime import datetime, timezone
import asyncio

from sqlalchemy import select

from celery_app import celery_app
from database_celery import get_session
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from requests_handler.process_realization import process_realization
from requests_handler.stocks import process_stocks
from utils.token_crypto import decrypt_token
from core.logger import setup_logger

logger = setup_logger(__name__, "processor.log")

""" def run_async(coro):
    return asyncio.run(coro) """

@celery_app.task
def process_job(job_id: str):
    return asyncio.run(_process_job(job_id))


async def _process_job(job_id: str):
    logger.info(f"[JOB START] job_id={job_id}")
    session = await get_session()
    job = await session.get(SyncJob, job_id)
    

    if not job:
        return
    
    logger.info(f"[JOB FETCHED] id={job.id} status={job.status} entity={job.entity}")

    # ❗ уже обработан
    if job.status in ("processing", "done"):
        logger.warning(f"[JOB SKIP] already processed status={job.status}")
        return

    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    await session.commit()
    logger.info(f"[JOB STATUS] -> processing, started_at={job.started_at}")

    # 🔑 токен
    token = await session.get(APIToken, job.token_id)

    if not token or not token.is_valid:
        job.status = "failed"
        job.error = "Invalid token"
        await session.commit()
        return
    logger.info(f"[TOKEN] token_id={job.token_id} valid={token.is_valid if token else None}")

    wb_token = decrypt(token.encrypted_token)
    logger.info(f"[JOB EXEC] entity={job.entity} payload={job.payload}")
    try:
        if job.entity == "stocks":
            await process_stocks(session, job, wb_token)

        elif job.entity == "realization":
            await process_realization(session, job, wb_token)

        # ✅ обновляем sync state
        await update_sync_state(session, job)
        logger.info(f"[JOB] state updated for entity={job.entity}")

        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        logger.info(f"[JOB SUCCESS] entity={job.entity}")

    except RuntimeError as e:
        if str(e) == "rate_limit":
            logger.warning("[RATE LIMIT] updating state")

            await update_sync_state_error(session, job, "rate_limit")

            job.status = "failed"
            job.error = "rate_limit"

            return

    finally:
        logger.info(f"[JOB DONE] id={job.id} finished_at={job.finished_at}")
        await session.commit()
        await session.close()

def decrypt(token: str) -> str:
    return decrypt_token(token)

async def update_sync_state(session, job):
    logger.info(f"[STATE] updating for entity={job.entity}")

    result = await session.execute(
        select(UserSyncState).where(
            UserSyncState.user_id == job.user_id,
            UserSyncState.token_id == job.token_id,
            UserSyncState.entity == job.entity
        )
    )

    state = result.scalar_one_or_none()

    if not state:
        logger.warning("[STATE] not found → creating new")
        state = UserSyncState(
            user_id=job.user_id,
            token_id=job.token_id,
            entity=job.entity,
        )
        session.add(state)
    else:
        logger.info(f"[STATE] found id={state.id}")

    now = datetime.now(timezone.utc)

    logger.info(f"[STATE BEFORE] last_sync_at={state.last_sync_at}")

    state.last_sync_at = now
    state.last_success_at = now
    state.last_error = None

    logger.info(f"[STATE AFTER] last_sync_at={state.last_sync_at}")


async def update_sync_state_error(session, job, error):
    result = await session.execute(
        select(UserSyncState).where(
            UserSyncState.user_id == job.user_id,
            UserSyncState.token_id == job.token_id,
            UserSyncState.entity == job.entity
        )
    )

    state = result.scalar_one_or_none()

    if not state:
        state = UserSyncState(
            user_id=job.user_id,
            token_id=job.token_id,
            entity=job.entity,
        )
        session.add(state)

    logger.info(f"[STATE ERROR BEFORE] last_error={state.last_error}")

    now = datetime.now(timezone.utc)

    state.last_sync_at = now
    state.last_error = error

    logger.info(f"[STATE ERROR AFTER] last_error={state.last_error}")