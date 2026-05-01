from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_stock_service import save_stocks

logger = setup_logger(__name__, "wb_api_processor.log")


async def process_stock(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[STOCK] start")

    client = WBClient(token)
    try:
        data: Dict[str, Any] = await client.get_stock(job.payload) # type: ignore

        logger.debug(data)
        items = data["data"]["items"]

        await save_stocks(session, job.user_id, token.id, items)
        logger.info("[STOCK] success")
    except Exception as e:
        logger.info(f"[STOCK] error: {e}")
        job.status = "failed"
        job.error = str(e)
        raise