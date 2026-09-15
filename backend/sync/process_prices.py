from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.wb_price_service import (
    prune_price_snapshot,
    save_price_snapshot,
    snapshot_timestamp,
)


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_prices(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[PRICES] start token_id=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    limit = min(max(int(request_payload.get("limit") or 1000), 1), 1000)
    offset = max(int(request_payload.get("offset") or 0), 0)
    observed_at = snapshot_timestamp(request_payload.get("snapshotAt"))
    request_payload["snapshotAt"] = observed_at.isoformat()

    total_loaded = 0
    total_changes = 0

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
                        "Wildberries prices response has unexpected shape",
                        endpoint="prices.list_goods",
                    )

                items = response.get("data", {}).get("listGoods", [])
                if not isinstance(items, list):
                    raise WBAPIError(
                        "Wildberries price list has unexpected shape",
                        endpoint="prices.list_goods",
                    )
                if not items:
                    break

                rows_seen, changes = await save_price_snapshot(
                    session,
                    user_id=job.user_id,
                    token_id=token.id,
                    items=items,
                    observed_at=observed_at,
                )
                total_loaded += rows_seen
                total_changes += changes

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
        # A finished snapshot should not resume from its old offset on the next
        # scheduled run. State scheduling builds a fresh payload, but clearing
        # the continuation here also keeps the completed job self-describing.
        job.payload = {
            "limit": limit,
            "offset": 0,
            "completedSnapshotAt": datetime.now(timezone.utc).isoformat(),
        }
        await session.flush()

        logger.info(
            "[PRICES] success token_id=%s rows=%s changes=%s removed=%s",
            token.id,
            total_loaded,
            total_changes,
            removed,
        )
    except Exception as exc:
        logger.warning(
            "[PRICES] failed token_id=%s offset=%s error=%s",
            token.id,
            offset,
            type(exc).__name__,
        )
        raise
