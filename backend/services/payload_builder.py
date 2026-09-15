from datetime import date, datetime, timedelta, timezone
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


def _prices_payload(
    _last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    # Prices endpoint is a current-state listing. Each scheduled run must begin
    # from offset zero; the processor adds snapshotAt only while resuming that
    # specific durable job.
    return {"limit": 1000, "offset": 0}


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


def _sales_funnel_payload(
    _last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=config.WB_FUNNEL_LOOKBACK_DAYS - 1)
    return {
        "selectedPeriod": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "nm_ids": [],
        "nm_offset": 0,
    }


def _cursor_date(source_cursor: Optional[dict]) -> date | None:
    if not source_cursor or not source_cursor.get("completedThrough"):
        return None
    try:
        return date.fromisoformat(str(source_cursor["completedThrough"])[:10])
    except ValueError:
        return None


def _paid_storage_payload(
    _last_sync_at: Optional[datetime],
    source_cursor: Optional[dict] = None,
) -> dict:
    # Storage charges for the current Moscow day can still change. Sync only
    # completed calendar days and refresh the latest documented report window.
    end_date = datetime.now(MOSCOW_TZ).date() - timedelta(days=1)
    cursor = _cursor_date(source_cursor)
    recent_start = end_date - timedelta(days=config.WB_STORAGE_REFRESH_DAYS - 1)

    if cursor is None:
        start_date = end_date - timedelta(days=config.WB_STORAGE_BACKFILL_DAYS - 1)
    elif cursor < recent_start:
        # Catch up a gap first. The processor will split it into <=8-day tasks.
        start_date = cursor + timedelta(days=1)
    else:
        # Normal steady state: replace the recent window to absorb WB revisions.
        start_date = recent_start

    if start_date > end_date:
        start_date = end_date

    return {
        "dateFrom": start_date.isoformat(),
        "dateTo": end_date.isoformat(),
        "currentDateFrom": start_date.isoformat(),
        "taskId": None,
        "taskDateFrom": None,
        "taskDateTo": None,
        "completedThrough": cursor.isoformat() if cursor else None,
    }


PAYLOAD_BUILDERS: dict[
    str,
    Callable[[Optional[datetime], Optional[dict]], dict],
] = {
    "products": _products_payload,
    "prices": _prices_payload,
    "stocks": _stocks_payload,
    "realization": _realization_payload,
    "orders": _operational_payload,
    "sales": _operational_payload,
    "advertising": _advertising_payload,
    "sales_funnel": _sales_funnel_payload,
    "paid_storage": _paid_storage_payload,
}


def build_payload_for_entity(
    entity: str,
    last_sync_at: Optional[datetime] = None,
    source_cursor: Optional[dict] = None,
) -> dict:
    builder = PAYLOAD_BUILDERS.get(entity, _realization_payload)
    return builder(last_sync_at, source_cursor)
