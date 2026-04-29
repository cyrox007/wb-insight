from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken

logger = setup_logger(__name__, "wb_api_processor.log")

async def process_products(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[PRODUCTS] start")

    client = WBClient(token)
    
    # Инициализируем payload если он не задан
    if not job.payload:
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
        total_loaded = 0
        while True:
            data: dict = await client.get_products(job.payload)

            logger.debug(f"[PRODUCTS] loaded batch: {len(data.get('cards', []))} items")

            await save_products(session, job.user_id, token.id, data['cards'])

            products_count = len(data.get('cards', []))

            total_loaded += products_count

            # Если загрузили меньше чем лимит, значит это последняя страница
            cursor_limit = job.payload.get('settings', {}).get('cursor', {}).get('limit', 100)
            if products_count < cursor_limit:
                logger.info(f"[PRODUCTS] last page reached, total loaded: {total_loaded}")
                break

            # Обновляем курсор для следующей страницы
            # Wildberries API возвращает данные о курсоре в ответе
            if 'cursor' in data and 'next' in data['cursor']:
                job.payload['settings']['cursor']['data'] = data['cursor']['next']
                logger.debug(f"[PRODUCTS] next cursor: {data['cursor']['next']}")
            else:
                logger.info(f"[PRODUCTS] no more pages, total loaded: {total_loaded}")
                break

        logger.info(f"[PRODUCTS] success, total products: {total_loaded}")
    
    except Exception as e:
        logger.error(f"[PRODUCTS] error: {e}")
        job.status = "failed"
        job.error = str(e)
        raise