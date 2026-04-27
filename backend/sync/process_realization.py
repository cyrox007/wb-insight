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

        logger.info(data)
        await save_realization(session, job.user_id, data)
    
    except Exception as e:
        logger.error(f"Случилась ошибка: {e}")
        raise
    
    finally:
        logger.info("[REALIZATION] success")