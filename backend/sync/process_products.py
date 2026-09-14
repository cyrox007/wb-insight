from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_products_service import save_products


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_products(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[PRODUCTS] start token_id=%s", token.id)

    payload = job.payload or {
        "settings": {
            "sort": {"ascending": True},
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }
    job.payload = payload

    try:
        total_loaded = 0
        async with WBClient(token) as client:
            while True:
                data = await client.get_products(payload)
                if not isinstance(data, dict):
                    raise WBAPIError(
                        "Wildberries product response has unexpected shape",
                        endpoint="content.cards_list",
                    )

                cards = data.get("cards", [])
                if not isinstance(cards, list):
                    raise WBAPIError(
                        "Wildberries product cards have unexpected shape",
                        endpoint="content.cards_list",
                    )

                await save_products(session, job.user_id, token.id, cards)
                total_loaded += len(cards)

                cursor_data = data.get("cursor") or {}
                cursor_total = int(cursor_data.get("total") or 0)
                cursor = payload.setdefault("settings", {}).setdefault("cursor", {})
                cursor_limit = int(cursor.get("limit") or 100)

                if cursor_total < cursor_limit:
                    break

                updated_at = cursor_data.get("updatedAt")
                nm_id = cursor_data.get("nmID")
                if not updated_at or nm_id is None:
                    raise WBAPIError(
                        "Wildberries product cursor is incomplete",
                        endpoint="content.cards_list",
                    )

                # WB expects continuation fields directly inside settings.cursor.
                cursor["updatedAt"] = updated_at
                cursor["nmID"] = nm_id
                cursor.pop("data", None)

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
