from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_stock_service import save_stocks

logger = setup_logger(__name__, "wb_api_processor.log")

async def process_products(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[PRODUCTS] start")

    client = WBClient(token)
    job.payload = {
    "settings": {
            "sort": {
                "ascending": True
            },
            "cursor": {
                "limit": 100
            },
            "filter": {
                "withPhoto": -1
            }
        }
    }
    try:
        data = await client.get_products(job.payload)

        logger.debug(data)

        await save_stocks(session, job.user_id, token.id, data)

        if data['cursor']['total'] >= 100:
            # надо брать по пачке из 100 штук до тех пор пока тотал не станет мешьше 100
        logger.info("[PRODUCTS] success")
    except Exception as e:
        logger.info(f"[PRODUCTS] error: {e}")
        job.status = "failed"
        job.error = str(e)
        raise