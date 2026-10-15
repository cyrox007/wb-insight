from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.wb_product import WbProduct
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_sales_funnel_service import save_sales_funnel_history
from settings import config


logger = setup_logger(__name__, "wb_api_processor.log")


async def _account_nm_ids(session: AsyncSession, token_id) -> list[int]:
    result = await session.execute(
        select(WbProduct.nm_id)
        .where(WbProduct.token_id == token_id)
        .order_by(WbProduct.nm_id)
    )
    return [int(value) for value in result.scalars().all() if value]


def _valid_nm_ids(values: Sequence[object]) -> list[int]:
    result: list[int] = []
    for value in values:
        try:
            nm_id = int(value)
        except (TypeError, ValueError):
            continue
        if nm_id > 0:
            result.append(nm_id)
    return sorted(set(result))


async def process_sales_funnel(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    payload = dict(job.payload or {})
    selected_period = payload.get("selectedPeriod") or {}
    start = selected_period.get("start") if isinstance(selected_period, dict) else None
    end = selected_period.get("end") if isinstance(selected_period, dict) else None
    if not start or not end:
        raise ValueError(
            "Для синхронизации воронки продаж требуются selectedPeriod.start и selectedPeriod.end"
        )

    nm_ids = _valid_nm_ids(payload.get("nm_ids") or [])
    if not nm_ids:
        nm_ids = await _account_nm_ids(session, token.id)

    offset = max(0, int(payload.get("nm_offset", 0) or 0))
    total_rows = 0
    batch_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={
            "period_from": start,
            "period_to": end,
            "products": len(nm_ids),
            "nm_offset": offset,
        },
    )

    if not nm_ids:
        await trace_sync_stage(
            job=job,
            token=token,
            step="source_empty",
            status="warning",
            severity="warning",
            error_code="FUNNEL_PRODUCTS_MISSING",
            message="В кабинете нет товаров для запроса воронки продаж",
        )
        logger.info("[ВОРОНКА] нет товаров идентификатор_токена=%s", token.id)
        return

    async with WBClient(token) as client:
        while offset < len(nm_ids):
            batch = nm_ids[offset : offset + config.WB_FUNNEL_NM_BATCH_SIZE]
            response = await client.get_sales_funnel_history(
                {
                    "selectedPeriod": {"start": str(start), "end": str(end)},
                    "nmIds": batch,
                    "skipDeletedNm": True,
                    "aggregationLevel": "day",
                }
            )
            rows = response if isinstance(response, list) else []
            batch_number += 1
            await trace_sync_stage(
                job=job,
                token=token,
                step="source_page_validated",
                status="success",
                output_data={
                    "batch": batch_number,
                    "nm_ids": batch,
                    "rows_received": len(rows),
                },
            )
            saved = await save_sales_funnel_history(
                session,
                job.user_id,
                token.id,
                rows,
            )
            total_rows += saved
            await trace_sync_stage(
                job=job,
                token=token,
                step="rows_persisted",
                status="success",
                output_data={
                    "batch": batch_number,
                    "rows_received": len(rows),
                    "rows_saved": saved,
                    "total_saved": total_rows,
                },
            )

            offset += len(batch)
            payload["nm_ids"] = nm_ids
            payload["nm_offset"] = offset
            await persist_job_checkpoint(session, job, payload)

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_completed",
        status="success",
        output_data={
            "products": len(nm_ids),
            "facts_saved": total_rows,
            "period_from": start,
            "period_to": end,
        },
    )
    logger.info(
        "[ВОРОНКА] завершено идентификатор_токена=%s товаров=%s фактов=%s период=%s..%s",
        token.id,
        len(nm_ids),
        total_rows,
        start,
        end,
    )