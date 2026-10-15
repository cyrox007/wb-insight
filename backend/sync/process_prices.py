from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_price_service import (
    prune_price_snapshot,
    save_price_snapshot,
    snapshot_timestamp,
)


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_prices(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[ЦЕНЫ] запуск идентификатор_токена=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    limit = min(max(int(request_payload.get("limit") or 1000), 1), 1000)
    offset = max(int(request_payload.get("offset") or 0), 0)
    observed_at = snapshot_timestamp(request_payload.get("snapshotAt"))
    request_payload["snapshotAt"] = observed_at.isoformat()

    total_loaded = 0
    total_changes = 0
    page_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={
            "limit": limit,
            "offset": offset,
            "snapshot_at": observed_at,
        },
    )

    try:
        async with WBClient(token) as client:
            while True:
                api_payload = {
                    "limit": limit,
                    "offset": offset,
                }
                response = await client.get_prices(api_payload)

                if response == []:
                    break
                if not isinstance(response, dict):
                    raise WBAPIError(
                        "Wildberries вернул цены в неожиданном формате",
                        endpoint="prices.list_goods",
                    )

                items = response.get("data", {}).get("listGoods", [])
                if not isinstance(items, list):
                    raise WBAPIError(
                        "Wildberries вернул список цен в неожиданном формате",
                        endpoint="prices.list_goods",
                    )
                if not items:
                    break

                page_number += 1
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="source_page_validated",
                    status="success",
                    output_data={
                        "page": page_number,
                        "items": len(items),
                        "offset": offset,
                    },
                )
                rows_seen, changes = await save_price_snapshot(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    items=items,
                    observed_at=observed_at,
                )
                total_loaded += rows_seen
                total_changes += changes
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="rows_persisted",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows_seen": rows_seen,
                        "changes": changes,
                        "snapshot_at": observed_at,
                    },
                )

                page_size = len(items)
                offset += limit
                request_payload["limit"] = limit
                request_payload["offset"] = offset
                await persist_job_checkpoint(session, job, request_payload)

                if page_size < limit:
                    break

        removed = await prune_price_snapshot(
            session,
            token_id=token.id,
            observed_at=observed_at,
        )
        await trace_sync_stage(
            job=job,
            token=token,
            step="snapshot_pruned",
            status="success",
            output_data={
                "removed_stale_rows": removed,
                "snapshot_at": observed_at,
            },
        )

        # Завершённый снимок не должен продолжаться со старого offset при следующем
        # плановом запуске. Планировщик создаёт свежий payload, а сброс здесь ещё и
        # делает завершённую задачу самодостаточной для последующей диагностики.
        job.payload = {
            "limit": limit,
            "offset": 0,
            "completedSnapshotAt": datetime.now(timezone.utc).isoformat(),
        }
        await session.flush()

        await trace_sync_stage(
            job=job,
            token=token,
            step="source_read_completed",
            status="success",
            output_data={
                "pages": page_number,
                "rows": total_loaded,
                "changes": total_changes,
                "removed": removed,
            },
        )
        logger.info(
            "[ЦЕНЫ] завершено идентификатор_токена=%s строк=%s изменений=%s удалено=%s",
            token.id,
            total_loaded,
            total_changes,
            removed,
        )
    except Exception as exc:
        logger.warning(
            "[ЦЕНЫ] ошибка идентификатор_токена=%s смещение=%s тип_ошибки=%s",
            token.id,
            offset,
            type(exc).__name__,
        )
        raise