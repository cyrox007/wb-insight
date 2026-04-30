from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_report_service import save_realization

logger = setup_logger(__name__, "wb_api_processor.log")

async def process_realization(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[REALIZATION] start")

    client = WBClient(token)
    try:
        data = await client.get_realization(job.payload)

        logger.debug(data)

        await save_realization(session, job.user_id, token.id, data)
        logger.info("[REALIZATION] success")
    except Exception as e:
        logger.info(f"[REALIZATION] error: {e}")
        job.status = "failed"
        job.error = str(e)
        raise
