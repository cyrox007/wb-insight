from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_stock_service import save_stocks


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_stock(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[ОСТАТКИ] запуск идентификатор_токена=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    limit = int(request_payload.get("limit") or 250000)
    offset = int(request_payload.get("offset") or 0)
    total_loaded = 0
    page_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={"limit": limit, "offset": offset},
    )

    try:
        async with WBClient(token) as client:
            while True:
                request_payload["limit"] = limit
                request_payload["offset"] = offset
                response = await client.get_stock(request_payload)

                if response == []:
                    await trace_sync_stage(
                        job=job,
                        token=token,
                        step="source_exhausted",
                        status="success",
                        output_data={"pages": page_number, "rows": total_loaded},
                    )
                    break
                if not isinstance(response, dict):
                    raise WBAPIError(
                        "Wildberries вернул остатки в неожиданном формате",
                        endpoint="analytics.stocks_warehouses",
                    )

                items = response.get("data", {}).get("items", [])
                if not isinstance(items, list):
                    raise WBAPIError(
                        "Wildberries вернул список остатков в неожиданном формате",
                        endpoint="analytics.stocks_warehouses",
                    )
                if not items:
                    break

                page_number += 1
                page_size = len(items)
                next_offset = offset + page_size
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="source_page_validated",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows": page_size,
                        "offset": offset,
                        "next_offset": next_offset,
                    },
                )
                await save_stocks(session, job.user_id, token.id, items)
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="rows_persisted",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows_submitted": page_size,
                    },
                )
                request_payload["offset"] = next_offset
                await persist_job_checkpoint(session, job, request_payload)

                total_loaded += page_size
                offset = next_offset
                if page_size < limit:
                    break

        await trace_sync_stage(
            job=job,
            token=token,
            step="source_read_completed",
            status="success",
            output_data={"pages": page_number, "rows": total_loaded},
        )
        logger.info(
            "[ОСТАТКИ] завершено идентификатор_токена=%s строк=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[ОСТАТКИ] ошибка идентификатор_токена=%s тип_ошибки=%s",
            token.id,
            type(exc).__name__,
        )
        raise