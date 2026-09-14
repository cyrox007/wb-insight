from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.wb_advertising_ingest_service import save_advertising_fullstats


logger = setup_logger(__name__, "wb_api_processor.log")
CAMPAIGN_BATCH_SIZE = 50
ELIGIBLE_STATUSES = "7,9,11"
ACTIVE_STATUSES = {9, 11}
COMPLETED_STATUS = 7


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _campaign_ids(response: Any, begin_date: date) -> list[int]:
    adverts = response.get("adverts", []) if isinstance(response, dict) else response
    if not isinstance(adverts, list):
        return []

    result: list[int] = []
    for item in adverts:
        if not isinstance(item, dict):
            continue

        raw_id = item.get("id", item.get("advertId"))
        try:
            campaign_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if campaign_id <= 0:
            continue

        raw_status = item.get("status")
        try:
            status = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            status = None

        if status in ACTIVE_STATUSES or status is None:
            result.append(campaign_id)
            continue

        if status == COMPLETED_STATUS:
            timestamps = item.get("timestamps") or {}
            updated = _date(timestamps.get("updated")) if isinstance(timestamps, dict) else None
            if updated is not None and updated >= begin_date:
                result.append(campaign_id)

    return sorted(set(result))


async def process_advertising(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    payload = dict(job.payload or {})
    begin_date_raw = payload.get("beginDate")
    end_date = payload.get("endDate")
    begin_date = _date(begin_date_raw)
    if begin_date is None or not end_date:
        raise ValueError("advertising sync requires beginDate and endDate")

    campaign_ids = [
        int(value)
        for value in payload.get("campaign_ids", [])
        if str(value).isdigit() and int(value) > 0
    ]
    offset = max(0, int(payload.get("campaign_offset", 0) or 0))
    total_rows = 0

    async with WBClient(token) as client:
        if not campaign_ids:
            campaign_response = await client.get_advert_campaigns(
                {"statuses": ELIGIBLE_STATUSES}
            )
            campaign_ids = _campaign_ids(campaign_response, begin_date)
            offset = 0

        while offset < len(campaign_ids):
            batch = campaign_ids[offset : offset + CAMPAIGN_BATCH_SIZE]
            response = await client.get_advert_stats(
                {
                    "ids": ",".join(str(item) for item in batch),
                    "beginDate": begin_date.isoformat(),
                    "endDate": str(end_date),
                }
            )
            stats = response if isinstance(response, list) else []
            total_rows += await save_advertising_fullstats(
                session,
                job.user_id,
                token.id,
                stats,
            )

            offset += len(batch)
            payload["campaign_ids"] = campaign_ids
            payload["campaign_offset"] = offset
            await persist_job_checkpoint(session, job, payload)

    logger.info(
        "[ADVERTISING] success token_id=%s campaigns=%s facts=%s period=%s..%s",
        token.id,
        len(campaign_ids),
        total_rows,
        begin_date,
        end_date,
    )
