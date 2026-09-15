from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError
from integrations.wildberries.finance_client import WBFinanceClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.wb_finance_summary_service import (
    save_finance_balance,
    save_finance_report_summaries,
)


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_finance_summary(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
):
    logger.info("[FINANCE_SUMMARY] start token_id=%s", token.id)

    payload: dict[str, Any] = dict(job.payload or {})
    limit = min(max(int(payload.get("limit") or 1000), 1), 1000)
    offset = max(int(payload.get("offset") or 0), 0)
    observed_at = datetime.now(timezone.utc)
    loaded = 0

    try:
        async with WBFinanceClient(token) as client:
            if not payload.get("balanceFetched"):
                balance = await client.get_balance()
                if not isinstance(balance, dict):
                    raise WBAPIError(
                        "Wildberries finance balance response has unexpected shape",
                        endpoint="finance.balance",
                    )
                await save_finance_balance(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    payload=balance,
                    observed_at=observed_at,
                )
                payload["balanceFetched"] = True
                await persist_job_checkpoint(session, job, payload)

            while True:
                request_body = {
                    "dateFrom": payload["dateFrom"],
                    "dateTo": payload["dateTo"],
                    "limit": limit,
                    "offset": offset,
                    "period": payload.get("period") or "weekly",
                }
                page = await client.get_sales_reports_list(request_body)
                if page == []:
                    break
                if not isinstance(page, list):
                    raise WBAPIError(
                        "Wildberries finance report list has unexpected shape",
                        endpoint="finance.sales_reports_list",
                    )

                await save_finance_report_summaries(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    items=page,
                    observed_at=observed_at,
                )
                loaded += len(page)
                offset += len(page)
                payload["offset"] = offset
                await persist_job_checkpoint(session, job, payload)

                if len(page) < limit:
                    break

        job.payload = {
            "dateFrom": payload["dateFrom"],
            "dateTo": payload["dateTo"],
            "limit": limit,
            "offset": 0,
            "period": payload.get("period") or "weekly",
            "balanceFetched": False,
            "completedAt": datetime.now(timezone.utc).isoformat(),
        }
        await session.flush()
        logger.info(
            "[FINANCE_SUMMARY] success token_id=%s reports=%s",
            token.id,
            loaded,
        )
    except Exception as exc:
        logger.warning(
            "[FINANCE_SUMMARY] failed token_id=%s offset=%s error=%s",
            token.id,
            offset,
            type(exc).__name__,
        )
        raise
