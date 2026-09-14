from datetime import datetime, timezone
from typing import Callable, Optional


def _realization_payload(last_sync_at: Optional[datetime]) -> dict:
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


def _stocks_payload(_: Optional[datetime]) -> dict:
    return {
        "nmIds": [],
        "chrtIds": [],
        "limit": 250000,
        "offset": 0,
    }


def _products_payload(_: Optional[datetime]) -> dict:
    return {
        "settings": {
            "sort": {"ascending": True},
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }


PAYLOAD_BUILDERS: dict[str, Callable[[Optional[datetime]], dict]] = {
    "products": _products_payload,
    "stocks": _stocks_payload,
    "realization": _realization_payload,
}


def build_payload_for_entity(
    entity: str,
    last_sync_at: Optional[datetime] = None,
) -> dict:
    builder = PAYLOAD_BUILDERS.get(entity, _realization_payload)
    return builder(last_sync_at)
