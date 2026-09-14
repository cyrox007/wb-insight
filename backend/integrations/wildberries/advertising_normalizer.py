from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _booster_positions(campaign: dict[str, Any]) -> dict[tuple[date, int], Decimal]:
    result: dict[tuple[date, int], Decimal] = {}
    for item in campaign.get("boosterStats") or []:
        item_date = _date(item.get("date"))
        nm_id = _int(item.get("nm"), default=0)
        if item_date is None or nm_id <= 0:
            continue
        value = item.get("avg_position", item.get("avgPosition"))
        result[(item_date, nm_id)] = _decimal(value)
    return result


def flatten_fullstats_v3(
    campaigns: list[dict[str, Any]],
    user_id: UUID,
    token_id: UUID,
) -> list[dict[str, Any]]:
    """Flatten WB v3 campaign -> day -> app -> nms into DB fact rows."""
    rows: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc)

    for campaign in campaigns or []:
        campaign_id = _int(campaign.get("advertId"), default=0)
        if campaign_id <= 0:
            continue
        currency = str(campaign.get("currency") or "").strip().upper() or None
        booster_positions = _booster_positions(campaign)

        for day in campaign.get("days") or []:
            day_date = _date(day.get("date"))
            if day_date is None:
                continue

            for app in day.get("apps") or []:
                platform_type = _int(app.get("appType"), default=0)

                for nm in app.get("nms") or []:
                    nm_id = _int(nm.get("nmId"), default=0)
                    if nm_id <= 0:
                        continue

                    rows.append(
                        {
                            "user_id": user_id,
                            "token_id": token_id,
                            "campaign_id": campaign_id,
                            "nm_id": nm_id,
                            "date": day_date,
                            "platform_type": platform_type,
                            "currency": currency,
                            "product_name": (
                                str(nm["name"]) if nm.get("name") is not None else None
                            ),
                            "company": None,
                            "views": _int(nm.get("views")),
                            "clicks": _int(nm.get("clicks")),
                            "ctr": _decimal(nm.get("ctr")),
                            "cpc": _decimal(nm.get("cpc")),
                            "amount": _decimal(nm.get("sum")),
                            "added_to_cart": _int(nm.get("atbs")),
                            "orders": _int(nm.get("orders")),
                            "canceled": _int(nm.get("canceled")),
                            "cr": _decimal(nm.get("cr")),
                            "shks": _int(nm.get("shks")),
                            "orders_amount": _decimal(nm.get("sum_price")),
                            "avg_position": booster_positions.get((day_date, nm_id)),
                            "created_at": created_at,
                        }
                    )

    return rows
