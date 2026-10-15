from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_operational_service import save_orders, save_sales


logger = setup_logger(__name__, "wb_api_processor.log")
OPERATIONAL_PAGE_LIMIT = 80000

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
        raise ValueError(f"Для синхронизации '{entity}' требуется dateFrom")

    total_saved = 0
    pages = 0
    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={"date_from": current_cursor, "entity": entity},
    )

    while True:
        rows = await fetch_page(payload)
        if not rows:
            await trace_sync_stage(
                job=job,
                token=token,
                step="source_exhausted",
                status="success",
                output_data={"pages": pages, "rows_saved": total_saved},
            )
            break

        pages += 1
        next_cursor_raw = rows[-1].get("lastChangeDate")
        if not next_cursor_raw:
            raise RuntimeError(
                f"В ответе WB '{entity}' отсутствует lastChangeDate в последней строке"
            )
        next_cursor = str(next_cursor_raw)

        if next_cursor < current_cursor:
            raise RuntimeError(
                f"Курсор lastChangeDate WB для '{entity}' переместился назад"
            )

        await trace_sync_stage(
            job=job,
            token=token,
            step="source_page_validated",
            status="success",
            output_data={
                "page": pages,
                "rows": len(rows),
                "current_cursor": current_cursor,
                "next_cursor": next_cursor,
            },
        )
        saved = await save_page(session, job.user_id, token.id, rows)
        total_saved += saved
        await trace_sync_stage(
            job=job,
            token=token,
            step="rows_persisted",
            status="success",
            output_data={
                "page": pages,
                "rows_received": len(rows),
                "rows_saved": saved,
                "total_saved": total_saved,
            },
        )

        payload["dateFrom"] = next_cursor
        payload["flag"] = 0
        await persist_job_checkpoint(session, job, payload)

        if next_cursor == current_cursor:
            if len(rows) >= OPERATIONAL_PAGE_LIMIT:
                raise RuntimeError(
                    f"Курсор WB '{entity}' остановился на полной странице; пропуск данных запрещён"
                )
            logger.info(
                "[%s] достигнута включительная граница курсора идентификатор_токена=%s страниц=%s",
                entity.upper(),
                token.id,
                pages,
            )
            break

        current_cursor = next_cursor

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_completed",
        status="success",
        output_data={
            "pages": pages,
            "rows_saved": total_saved,
            "cursor": payload.get("dateFrom"),
        },
    )
    logger.info(
        "[%s] завершено идентификатор_токена=%s страниц=%s строк=%s курсор=%s",
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