from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def normalize_paid_storage_rows(
    data: list[dict[str, Any]],
    user_id: UUID,
    token_id: UUID,
    task_id: str | None,
) -> list[dict[str, Any]]:
    """Нормализует актуальный отчёт Wildberries по платному хранению.

    Новые ключи не придумываются. Строки без корректной даты отчёта нельзя
    отнести к периоду замены, поэтому они игнорируются.
    """
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []

    for raw in data:
        row_date = _date(raw.get("date"))
        if row_date is None:
            continue

        result.append(
            {
                "user_id": user_id,
                "token_id": token_id,
                "source_task_id": task_id,
                "date": row_date,
                "log_warehouse_coef": _decimal(raw.get("logWarehouseCoef")),
                "office_id": _int(raw.get("officeId")),
                "warehouse": _text(raw.get("warehouse")),
                "warehouse_coef": _decimal(raw.get("warehouseCoef")),
                "gi_id": _int(raw.get("giId")),
                "chrt_id": _int(raw.get("chrtId")),
                "size": _text(raw.get("size")),
                "barcode": _text(raw.get("barcode")),
                "subject": _text(raw.get("subject")),
                "brand": _text(raw.get("brand")),
                "vendor_code": _text(raw.get("vendorCode")),
                "nm_id": _int(raw.get("nmId")),
                "volume": _decimal(raw.get("volume")),
                "calc_type": _text(raw.get("calcType")),
                "warehouse_price": _decimal(raw.get("warehousePrice")) or Decimal("0"),
                "barcodes_count": _int(raw.get("barcodesCount")),
                "pallet_place_code": _int(raw.get("palletPlaceCode")),
                "pallet_count": _decimal(raw.get("palletCount")),
                "original_date": _date(raw.get("originalDate")),
                "loyalty_discount": _decimal(raw.get("loyaltyDiscount")),
                "tariff_fix_date": _date(raw.get("tariffFixDate")),
                "tariff_lower_date": _date(raw.get("tariffLowerDate")),
                "created_at": now,
                "updated_at": now,
            }
        )

    return result
