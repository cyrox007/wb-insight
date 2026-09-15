from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from settings import config


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
OPERATIONAL_BACKFILL_DAYS = 89
FINANCE_DETAIL_BACKFILL_DAYS = 120
FINANCE_DETAIL_REFRESH_DAYS = 14
FINANCE_REPORTS_AVAILABLE_FROM = date(2025, 1, 1)
FINANCE_REPORT_REFRESH_DAYS = 45


def _realization_payload(
    last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    today = datetime.now(MOSCOW_TZ).date()
    if last_sync_at is None:
        date_from = today - timedelta(days=FINANCE_DETAIL_BACKFILL_DAYS - 1)
    else:
        # Finance rows can be corrected after the first publication. Refresh a
        # rolling tail instead of assuming the last successful request froze it.
        date_from = min(
            last_sync_at.astimezone(MOSCOW_TZ).date(),
            today,
        ) - timedelta(days=FINANCE_DETAIL_REFRESH_DAYS - 1)

    return {
        "dateFrom": date_from.isoformat(),
        "dateTo": today.isoformat(),
        "limit": 100000,
        "rrdId": 0,
        "period": "daily",
    }


def _finance_summary_payload(
    last_sync_at: Optional[datetime],
    _source_cursor: Optional[dict] = None,
) -> dict:
    today = datetime.now(MOSCOW_TZ).date()
    if last_sync_at is None:
        date_from = FINANCE_REPORTS_AVAILABLE_FROM
    else:
        date_from = max(
            FINANCE_REPORTS_AVAILABLE_FROM,
            today - timedelta(days=FINANCE_REPORT_REFRESH_DAYS - 1),
        )
    return {
        "dateFrom": date_from.isoformat(),
        "dateTo": today.isoformat(),
        "limit": 1000,
        "offset": 0,
        "period": "weekly",
        "balanceFetched": False,
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
    end_date = datetime.now(MOSCOW_TZ).date() - timedelta(days=1)
    cursor = _cursor_date(source_cursor)
    recent_start = end_date - timedelta(days=config.WB_STORAGE_REFRESH_DAYS - 1)

    if cursor is None:
        start_date = end_date - timedelta(days=config.WB_STORAGE_BACKFILL_DAYS - 1)
    elif cursor < recent_start:
        start_date = cursor + timedelta(days=1)
    else:
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
    "finance_summary": _finance_summary_payload,
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
