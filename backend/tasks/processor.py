from celery_app import celery_app
import asyncio

from requests_handler.process_realization import process_realization
from requests_handler.stocks import process_stocks
from utils.token_crypto import decrypt_token

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def process_job(self, job_id: str):
    asyncio.run(_process_job(job_id))


from datetime import datetime
from sqlalchemy import select

from database import Database
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState


async def _process_job(job_id: str):
    # async with Database.get_session() as session:
    session = await Database.get_session()
    job = await session.get(SyncJob, job_id)

    if not job:
        return

    # ❗ уже обработан
    if job.status in ("processing", "done"):
        return

    job.status = "processing"
    job.started_at = datetime.utcnow()
    await session.commit()

    # 🔑 токен
    token = await session.get(APIToken, job.token_id)

    if not token or not token.is_valid:
        job.status = "failed"
        job.error = "Invalid token"
        await session.commit()
        return

    wb_token = decrypt(token.encrypted_token)

    try:
        if job.entity == "stocks":
            await process_stocks(session, job, wb_token)

        elif job.entity == "realization":
            await process_realization(session, job, wb_token)

        # ✅ обновляем sync state
        await update_sync_state(session, job)

        job.status = "done"
        job.finished_at = datetime.utcnow()

    except Exception as e:
        job.status = "failed"
        job.error = str(e)

        raise  # 🔥 важно для retry

    finally:
        await session.commit()
        await session.close()

def decrypt(token: str) -> str:
    return decrypt_token(token)

async def update_sync_state(session, job):
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

    state.last_sync_at = datetime.utcnow()
    state.last_success_at = datetime.utcnow()
    state.last_error = None