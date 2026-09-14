from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_stock_service import save_stocks


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_stock(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[STOCK] start token_id=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    limit = int(request_payload.get("limit") or 250000)
    offset = int(request_payload.get("offset") or 0)
    total_loaded = 0

    try:
        async with WBClient(token) as client:
            while True:
                request_payload["limit"] = limit
                request_payload["offset"] = offset
                response = await client.get_stock(request_payload)

                if response == []:
                    break
                if not isinstance(response, dict):
                    raise WBAPIError(
                        "Wildberries stock response has unexpected shape",
                        endpoint="analytics.stocks_warehouses",
                    )

                items = response.get("data", {}).get("items", [])
                if not isinstance(items, list):
                    raise WBAPIError(
                        "Wildberries stock items have unexpected shape",
                        endpoint="analytics.stocks_warehouses",
                    )
                if not items:
                    break

                await save_stocks(session, job.user_id, token.id, items)
                page_size = len(items)
                total_loaded += page_size

                if page_size < limit:
                    break
                offset += page_size

        logger.info(
            "[STOCK] success token_id=%s items=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[STOCK] failed token_id=%s error=%s",
            token.id,
            type(exc).__name__,
        )
        raise
