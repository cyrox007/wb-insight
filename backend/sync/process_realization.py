from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.wb_report_service import save_realization


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_realization(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[REALIZATION] start token_id=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    request_payload.setdefault("limit", 100000)
    request_payload.setdefault("rrdId", 0)
    total_loaded = 0

    try:
        async with WBClient(token) as client:
            while True:
                page = await client.get_realization(request_payload)
                if page == []:
                    break
                if not isinstance(page, list):
                    raise WBAPIError(
                        "Wildberries finance response has unexpected shape",
                        endpoint="finance.sales_report_detailed",
                    )
                if not page:
                    break

                await save_realization(session, job.user_id, token.id, page)
                total_loaded += len(page)

                last_rrd_id = page[-1].get("rrdId")
                if not isinstance(last_rrd_id, int) or last_rrd_id <= 0:
                    raise WBAPIError(
                        "Wildberries finance response has no valid continuation rrdId",
                        endpoint="finance.sales_report_detailed",
                    )

                previous_rrd_id = int(request_payload.get("rrdId") or 0)
                if last_rrd_id <= previous_rrd_id:
                    raise WBAPIError(
                        "Wildberries finance cursor did not advance",
                        endpoint="finance.sales_report_detailed",
                    )
                request_payload["rrdId"] = last_rrd_id

        logger.info(
            "[REALIZATION] success token_id=%s rows=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[REALIZATION] failed token_id=%s error=%s",
            token.id,
            type(exc).__name__,
        )
        raise
