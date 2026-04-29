from datetime import datetime, timezone
from typing import Optional, Callable


def _date_range_payload(last_sync_at: Optional[datetime]) -> dict:
    now = datetime.now(timezone.utc)

    date_from = (
        last_sync_at.date().isoformat()
        if last_sync_at
        else now.date().isoformat()
    )

    return {
        "dateFrom": date_from,
        "dateTo": now.date().isoformat(),
    }


def _products_payload(_: Optional[datetime]) -> dict:
    return {
        "settings": {
            "sort": {"ascending": True},
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }


# 👉 единая точка конфигурации
PAYLOAD_BUILDERS: dict[str, Callable[[Optional[datetime]], dict]] = {
    "products": _products_payload,
    "stocks": _date_range_payload,
    "realization": _date_range_payload,
}

def build_payload_for_entity(
    entity: str,
    last_sync_at: Optional[datetime] = None
) -> dict:
    builder = PAYLOAD_BUILDERS.get(entity, _date_range_payload)
    return builder(last_sync_at)