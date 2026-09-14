from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_report_service import save_realization


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_realization(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[REALIZATION] start token_id=%s", token.id)

    try:
        async with WBClient(token) as client:
            data = await client.get_realization(job.payload)

        await save_realization(session, job.user_id, token.id, data)
        logger.info("[REALIZATION] success token_id=%s", token.id)
    except Exception as exc:
        logger.warning(
            "[REALIZATION] failed token_id=%s error=%s",
            token.id,
            type(exc).__name__,
        )
        raise
