from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError
from integrations.wildberries.finance_client import WBFinanceClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
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
    logger.info("[ФИНАНСОВАЯ_СВОДКА] запуск идентификатор_токена=%s", token.id)

    payload: dict[str, Any] = dict(job.payload or {})
    limit = min(max(int(payload.get("limit") or 1000), 1), 1000)
    offset = max(int(payload.get("offset") or 0), 0)
    observed_at = datetime.now(timezone.utc)
    loaded = 0
    page_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={
            "date_from": payload.get("dateFrom"),
            "date_to": payload.get("dateTo"),
            "period": payload.get("period") or "weekly",
            "offset": offset,
            "balance_fetched": bool(payload.get("balanceFetched")),
        },
    )

    try:
        async with WBFinanceClient(token) as client:
            if not payload.get("balanceFetched"):
                balance = await client.get_balance()
                if not isinstance(balance, dict):
                    raise WBAPIError(
                        "Wildberries вернул баланс в неожиданном формате",
                        endpoint="finance.balance",
                    )
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="balance_received",
                    status="success",
                    output_data={"fields": sorted(balance.keys())},
                )
                await save_finance_balance(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    payload=balance,
                    observed_at=observed_at,
                )
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="balance_persisted",
                    status="success",
                    output_data={"observed_at": observed_at},
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
                        "Wildberries вернул список финансовых отчётов в неожиданном формате",
                        endpoint="finance.sales_reports_list",
                    )

                page_number += 1
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="source_page_validated",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows": len(page),
                        "offset": offset,
                    },
                )
                await save_finance_report_summaries(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    items=page,
                    observed_at=observed_at,
                )
                loaded += len(page)
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="rows_persisted",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows_submitted": len(page),
                        "total_submitted": loaded,
                        "observed_at": observed_at,
                    },
                )
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
        await trace_sync_stage(
            job=job,
            token=token,
            step="source_read_completed",
            status="success",
            output_data={
                "pages": page_number,
                "reports": loaded,
                "period_from": payload["dateFrom"],
                "period_to": payload["dateTo"],
            },
        )
        logger.info(
            "[ФИНАНСОВАЯ_СВОДКА] завершено идентификатор_токена=%s отчётов=%s",
            token.id,
            loaded,
        )
    except Exception as exc:
        logger.warning(
            "[ФИНАНСОВАЯ_СВОДКА] ошибка идентификатор_токена=%s смещение=%s тип_ошибки=%s",
            token.id,
            offset,
            type(exc).__name__,
        )
        raise