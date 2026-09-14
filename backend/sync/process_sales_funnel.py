from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.wb_product import WbProduct
from services.sync_job_service import persist_job_checkpoint
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
        raise ValueError("sales funnel sync requires selectedPeriod.start/end")

    nm_ids = _valid_nm_ids(payload.get("nm_ids") or [])
    if not nm_ids:
        nm_ids = await _account_nm_ids(session, token.id)

    offset = max(0, int(payload.get("nm_offset", 0) or 0))
    total_rows = 0

    if not nm_ids:
        logger.info("[FUNNEL] no products token_id=%s", token.id)
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
            total_rows += await save_sales_funnel_history(
                session,
                job.user_id,
                token.id,
                rows,
            )

            offset += len(batch)
            payload["nm_ids"] = nm_ids
            payload["nm_offset"] = offset
            await persist_job_checkpoint(session, job, payload)

    logger.info(
        "[FUNNEL] success token_id=%s products=%s facts=%s period=%s..%s",
        token.id,
        len(nm_ids),
        total_rows,
        start,
        end,
    )
