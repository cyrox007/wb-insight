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


def flatten_sales_funnel_history(
    products: list[dict[str, Any]],
    user_id: UUID,
    token_id: UUID,
) -> list[dict[str, Any]]:
    """Преобразует историю аналитики WB v3 в одну строку на товар и день."""
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for item in products or []:
        product = item.get("product") or {}
        if not isinstance(product, dict):
            continue
        nm_id = _int(product.get("nmId"), default=0)
        if nm_id <= 0:
            continue

        currency = str(item.get("currency") or "").strip().upper() or None
        title = str(product.get("title")) if product.get("title") is not None else None
        vendor_code = (
            str(product.get("vendorCode")) if product.get("vendorCode") is not None else None
        )
        brand_name = (
            str(product.get("brandName")) if product.get("brandName") is not None else None
        )
        subject_id_raw = product.get("subjectId")
        subject_id = _int(subject_id_raw) if subject_id_raw is not None else None
        subject_name = (
            str(product.get("subjectName")) if product.get("subjectName") is not None else None
        )

        for history in item.get("history") or []:
            if not isinstance(history, dict):
                continue
            fact_date = _date(history.get("date"))
            if fact_date is None:
                continue

            rows.append(
                {
                    "user_id": user_id,
                    "token_id": token_id,
                    "nm_id": nm_id,
                    "date": fact_date,
                    "title": title,
                    "vendor_code": vendor_code,
                    "brand_name": brand_name,
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "currency": currency,
                    "open_count": _int(history.get("openCount")),
                    "cart_count": _int(history.get("cartCount")),
                    "order_count": _int(history.get("orderCount")),
                    "order_sum": _decimal(history.get("orderSum")),
                    "buyout_count": _int(history.get("buyoutCount")),
                    "buyout_sum": _decimal(history.get("buyoutSum")),
                    "buyout_percent": _decimal(history.get("buyoutPercent")),
                    "add_to_cart_conversion": _decimal(
                        history.get("addToCartConversion")
                    ),
                    "cart_to_order_conversion": _decimal(
                        history.get("cartToOrderConversion")
                    ),
                    "add_to_wishlist_count": _int(
                        history.get("addToWishlistCount")
                    ),
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return rows
