from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_products_service import save_products


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_products(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[PRODUCTS] start token_id=%s", token.id)

    if not job.payload:
        job.payload = {
            "settings": {
                "sort": {"ascending": True},
                "cursor": {"limit": 100},
                "filter": {"withPhoto": -1},
            }
        }

    try:
        total_loaded = 0
        async with WBClient(token) as client:
            while True:
                data = dict(await client.get_products(job.payload))
                cards = data.get("cards", [])
                logger.debug(
                    "[PRODUCTS] token_id=%s loaded_batch=%s",
                    token.id,
                    len(cards),
                )

                await save_products(session, job.user_id, token.id, cards)

                cards_count = len(cards)
                total_loaded += cards_count
                cursor_limit = (
                    job.payload.get("settings", {})
                    .get("cursor", {})
                    .get("limit", 100)
                )
                if cards_count < cursor_limit:
                    break

                cursor_data = data.get("cursor")
                if not cursor_data:
                    break

                job.payload["settings"]["cursor"]["data"] = {
                    "updatedAt": cursor_data.get("updatedAt"),
                    "nmID": cursor_data.get("nmID"),
                }

        logger.info(
            "[PRODUCTS] success token_id=%s total_products=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[PRODUCTS] failed token_id=%s error=%s",
            token.id,
            type(exc).__name__,
        )
        raise
