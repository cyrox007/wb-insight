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


def _campaign_ids(response: Any) -> list[int]:
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
        if campaign_id > 0:
            result.append(campaign_id)
    return sorted(set(result))


async def process_advertising(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    payload = dict(job.payload or {})
    begin_date = payload.get("beginDate")
    end_date = payload.get("endDate")
    if not begin_date or not end_date:
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
            campaign_ids = _campaign_ids(campaign_response)
            offset = 0

        while offset < len(campaign_ids):
            batch = campaign_ids[offset : offset + CAMPAIGN_BATCH_SIZE]
            response = await client.get_advert_stats(
                {
                    "ids": ",".join(str(item) for item in batch),
                    "beginDate": str(begin_date),
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
