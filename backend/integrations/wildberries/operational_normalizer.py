from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"WB operational row is missing required field: {key}")
    return str(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _boolean(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return bool(value)


def _datetime(value: Any, *, required: bool = False) -> datetime | None:
    if value in (None, ""):
        if required:
            raise ValueError("WB operational row is missing required datetime")
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            if required:
                raise ValueError("WB operational row contains invalid datetime") from exc
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MOSCOW_TZ)
    return parsed.astimezone(timezone.utc)


def _common(row: dict[str, Any], user_id: UUID, token_id: UUID) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "token_id": token_id,
        "warehouse_name": _text(row.get("warehouseName")),
        "warehouse_type": _text(row.get("warehouseType")),
        "country_name": _text(row.get("countryName")),
        "oblast_okrug_name": _text(row.get("oblastOkrugName")),
        "region_name": _text(row.get("regionName")),
        "supplier_article": _text(row.get("supplierArticle")),
        "nm_id": _integer(row.get("nmId")),
        "barcode": _text(row.get("barcode")),
        "category": _text(row.get("category")),
        "subject": _text(row.get("subject")),
        "brand": _text(row.get("brand")),
        "tech_size": _text(row.get("techSize")),
        "income_id": _integer(row.get("incomeID")),
        "is_supply": _boolean(row.get("isSupply")),
        "is_realization": _boolean(row.get("isRealization")),
        "total_price": _decimal(row.get("totalPrice")),
        "discount_percent": _decimal(row.get("discountPercent")),
        "spp": _decimal(row.get("spp")),
        "finished_price": _decimal(row.get("finishedPrice")),
        "price_with_disc": _decimal(row.get("priceWithDisc")),
        "sticker": _text(row.get("sticker")),
        "g_number": _text(row.get("gNumber")),
    }


def normalize_order_row(
    row: dict[str, Any],
    user_id: UUID,
    token_id: UUID,
) -> dict[str, Any]:
    values = _common(row, user_id, token_id)
    values.update(
        {
            "srid": _required_text(row, "srid"),
            "order_date": _datetime(row.get("date"), required=True),
            "last_change_date": _datetime(row.get("lastChangeDate"), required=True),
            "is_cancel": bool(_boolean(row.get("isCancel")) or False),
            "cancel_date": _datetime(row.get("cancelDate")),
        }
    )
    return values


def normalize_sale_row(
    row: dict[str, Any],
    user_id: UUID,
    token_id: UUID,
) -> dict[str, Any]:
    values = _common(row, user_id, token_id)
    values.update(
        {
            "sale_id": _required_text(row, "saleID"),
            "srid": _text(row.get("srid")),
            "sale_date": _datetime(row.get("date"), required=True),
            "last_change_date": _datetime(row.get("lastChangeDate"), required=True),
            "payment_sale_amount": _decimal(row.get("paymentSaleAmount")),
            "for_pay": _decimal(row.get("forPay")),
        }
    )
    return values
