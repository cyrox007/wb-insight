from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from settings import config


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
OPERATIONAL_BACKFILL_DAYS = 89


def _realization_payload(
    last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    date_from = (
        last_sync_at.date().isoformat()
        if last_sync_at
        else now.date().isoformat()
    )

    return {
        "dateFrom": date_from,
        "dateTo": now.date().isoformat(),
        "limit": 100000,
        "rrdId": 0,
        "period": "daily",
    }


def _stocks_payload(
    _last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    return {
        "nmIds": [],
        "chrtIds": [],
        "limit": 250000,
        "offset": 0,
    }


def _products_payload(
    _last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    return {
        "settings": {
            "sort": {"ascending": True},
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }


def _operational_payload(
    last_sync_at: Optional[datetime],
    source_cursor: Optional[dict] = None,
) -> dict:
    if source_cursor and source_cursor.get("dateFrom"):
        date_from = str(source_cursor["dateFrom"])
    else:
        now = datetime.now(timezone.utc)
        start = last_sync_at or (now - timedelta(days=OPERATIONAL_BACKFILL_DAYS))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        date_from = (
            start.astimezone(MOSCOW_TZ)
            .replace(tzinfo=None)
            .isoformat(timespec="seconds")
        )

    return {"dateFrom": date_from, "flag": 0}


def _advertising_payload(
    _last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    end_date = datetime.now(timezone.utc).date()
    begin_date = end_date - timedelta(days=config.WB_ADVERT_LOOKBACK_DAYS - 1)
    return {
        "beginDate": begin_date.isoformat(),
        "endDate": end_date.isoformat(),
        "campaign_ids": [],
        "campaign_offset": 0,
    }


PAYLOAD_BUILDERS: dict[
    str,
    Callable[[Optional[datetime], Optional[dict]], dict],
] = {
    "products": _products_payload,
    "stocks": _stocks_payload,
    "realization": _realization_payload,
    "orders": _operational_payload,
    "sales": _operational_payload,
    "advertising": _advertising_payload,
}


def build_payload_for_entity(
    entity: str,
    last_sync_at: Optional[datetime] = None,
    source_cursor: Optional[dict] = None,
) -> dict:
    builder = PAYLOAD_BUILDERS.get(entity, _realization_payload)
    return builder(last_sync_at, source_cursor)
