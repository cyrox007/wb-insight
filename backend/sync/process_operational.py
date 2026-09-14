from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.wb_operational_service import save_orders, save_sales


logger = setup_logger(__name__, "wb_api_processor.log")

FetchPage = Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]]
SavePage = Callable[
    [AsyncSession, Any, Any, list[dict[str, Any]]],
    Awaitable[int],
]


async def _process_operational_feed(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
    *,
    entity: str,
    fetch_page: FetchPage,
    save_page: SavePage,
) -> None:
    payload = dict(job.payload or {})
    current_cursor = str(payload.get("dateFrom") or "")
    if not current_cursor:
        raise ValueError(f"{entity} sync requires dateFrom")

    total_saved = 0
    pages = 0

    while True:
        rows = await fetch_page(payload)
        if not rows:
            break

        saved = await save_page(session, job.user_id, token.id, rows)
        total_saved += saved
        pages += 1

        next_cursor_raw = rows[-1].get("lastChangeDate")
        if not next_cursor_raw:
            raise RuntimeError(
                f"WB {entity} response did not provide lastChangeDate on the last row"
            )
        next_cursor = str(next_cursor_raw)

        if next_cursor < current_cursor:
            raise RuntimeError(
                f"WB {entity} lastChangeDate moved backwards"
            )

        payload["dateFrom"] = next_cursor
        payload["flag"] = 0
        await persist_job_checkpoint(session, job, payload)

        if next_cursor == current_cursor:
            logger.info(
                "[%s] reached inclusive cursor boundary token_id=%s pages=%s",
                entity.upper(),
                token.id,
                pages,
            )
            break

        current_cursor = next_cursor

    logger.info(
        "[%s] success token_id=%s pages=%s rows=%s cursor=%s",
        entity.upper(),
        token.id,
        pages,
        total_saved,
        payload.get("dateFrom"),
    )


async def process_orders(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    async with WBClient(token) as client:
        await _process_operational_feed(
            session,
            job,
            token,
            entity="orders",
            fetch_page=client.get_orders,
            save_page=save_orders,
        )


async def process_sales(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    async with WBClient(token) as client:
        await _process_operational_feed(
            session,
            job,
            token,
            entity="sales",
            fetch_page=client.get_sales,
            save_page=save_sales,
        )
