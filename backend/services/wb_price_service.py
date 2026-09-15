from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_price import WbPriceChange, WbPriceCurrent


PRICE_FIELDS = (
    "base_price",
    "discounted_price",
    "club_discounted_price",
    "discount",
    "club_discount",
)


def _decimal(value: Any, *, nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    try:
        return Decimal(str(0 if value is None else value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Некорректное числовое значение цены: {value!r}") from exc


def normalize_price_goods(items: list[dict]) -> list[dict]:
    """Flatten WB listGoods response to one deterministic row per size."""
    rows: list[dict] = []
    for goods in items:
        nm_id = goods.get("nmID")
        if nm_id is None:
            continue

        sizes = goods.get("sizes") or []
        if not isinstance(sizes, list):
            continue

        for size in sizes:
            if not isinstance(size, dict):
                continue
            size_id = size.get("sizeID")
            if size_id is None:
                continue

            rows.append(
                {
                    "nm_id": int(nm_id),
                    "size_id": int(size_id),
                    "vendor_code": goods.get("vendorCode"),
                    "tech_size_name": size.get("techSizeName"),
                    "currency": goods.get("currencyIsoCode4217"),
                    "base_price": _decimal(size.get("price")),
                    "discounted_price": _decimal(size.get("discountedPrice")),
                    "club_discounted_price": _decimal(
                        size.get("clubDiscountedPrice"), nullable=True
                    ),
                    "discount": _decimal(goods.get("discount")),
                    "club_discount": _decimal(goods.get("clubDiscount")),
                    "editable_size_price": bool(goods.get("editableSizePrice", False)),
                    "is_bad_turnover": bool(goods.get("isBadTurnover", False)),
                }
            )
    return rows


def _price_signature_from_row(row: dict) -> tuple:
    return tuple(row[field] for field in PRICE_FIELDS)


def _price_signature_from_model(row: WbPriceCurrent) -> tuple:
    return tuple(getattr(row, field) for field in PRICE_FIELDS)


async def save_price_snapshot(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    items: list[dict],
    observed_at: datetime,
) -> tuple[int, int]:
    """Persist one API page and append history only for actual price changes.

    Returns (rows_seen, changes_recorded).
    """
    rows = normalize_price_goods(items)
    if not rows:
        return 0, 0

    nm_ids = sorted({row["nm_id"] for row in rows})
    current_result = await session.execute(
        select(WbPriceCurrent).where(
            WbPriceCurrent.token_id == token_id,
            WbPriceCurrent.nm_id.in_(nm_ids),
        )
    )
    current_by_key = {
        (row.nm_id, row.size_id): row for row in current_result.scalars().all()
    }

    changes = 0
    for incoming in rows:
        key = (incoming["nm_id"], incoming["size_id"])
        current = current_by_key.get(key)

        if current is None:
            current = WbPriceCurrent(
                user_id=user_id,
                token_id=token_id,
                observed_at=observed_at,
                **incoming,
            )
            session.add(current)
            current_by_key[key] = current
            continue

        if _price_signature_from_model(current) != _price_signature_from_row(incoming):
            session.add(
                WbPriceChange(
                    user_id=user_id,
                    token_id=token_id,
                    nm_id=current.nm_id,
                    size_id=current.size_id,
                    vendor_code=incoming["vendor_code"],
                    tech_size_name=incoming["tech_size_name"],
                    currency=incoming["currency"],
                    previous_base_price=current.base_price,
                    base_price=incoming["base_price"],
                    previous_discounted_price=current.discounted_price,
                    discounted_price=incoming["discounted_price"],
                    previous_club_discounted_price=current.club_discounted_price,
                    club_discounted_price=incoming["club_discounted_price"],
                    previous_discount=current.discount,
                    discount=incoming["discount"],
                    previous_club_discount=current.club_discount,
                    club_discount=incoming["club_discount"],
                    changed_at=observed_at,
                )
            )
            changes += 1

        current.vendor_code = incoming["vendor_code"]
        current.tech_size_name = incoming["tech_size_name"]
        current.currency = incoming["currency"]
        current.base_price = incoming["base_price"]
        current.discounted_price = incoming["discounted_price"]
        current.club_discounted_price = incoming["club_discounted_price"]
        current.discount = incoming["discount"]
        current.club_discount = incoming["club_discount"]
        current.editable_size_price = incoming["editable_size_price"]
        current.is_bad_turnover = incoming["is_bad_turnover"]
        current.observed_at = observed_at

    await session.flush()
    return len(rows), changes


async def prune_price_snapshot(
    session: AsyncSession,
    *,
    token_id: UUID,
    observed_at: datetime,
) -> int:
    """Remove products/sizes absent from a fully completed current WB snapshot."""
    result = await session.execute(
        delete(WbPriceCurrent).where(
            WbPriceCurrent.token_id == token_id,
            WbPriceCurrent.observed_at < observed_at,
        )
    )
    await session.flush()
    return int(result.rowcount or 0)


def snapshot_timestamp(value: str | None = None) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)
