from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tokens_model import APIToken
from models.wb_price import WbPriceChange, WbPriceCurrent
from models.wb_product import WbProduct
from services.dashboard.account_scope import DashboardAccountScope


HISTORY_WINDOW_DAYS = 30
RECENT_CHANGE_LIMIT = 50


def _number(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _range(values) -> dict:
    clean = [Decimal(value) for value in values if value is not None]
    if not clean:
        return {"min": None, "max": None}
    return {"min": float(min(clean)), "max": float(max(clean))}


def _serialize_change(
    row: WbPriceChange,
    *,
    title: str | None,
    account_label: str,
) -> dict:
    return {
        "token_id": str(row.token_id),
        "account_label": account_label,
        "nm_id": row.nm_id,
        "product_name": title,
        "vendor_code": row.vendor_code,
        "size_id": row.size_id,
        "tech_size_name": row.tech_size_name,
        "currency": row.currency,
        "previous_base_price": _number(row.previous_base_price),
        "base_price": _number(row.base_price),
        "previous_discounted_price": _number(row.previous_discounted_price),
        "discounted_price": _number(row.discounted_price),
        "previous_club_discounted_price": _number(row.previous_club_discounted_price),
        "club_discounted_price": _number(row.club_discounted_price),
        "previous_discount": _number(row.previous_discount),
        "discount": _number(row.discount),
        "previous_club_discount": _number(row.previous_club_discount),
        "club_discount": _number(row.club_discount),
        "changed_at": row.changed_at.isoformat(),
    }


async def get_price_monitoring(
    session: AsyncSession,
    *,
    user_id: UUID,
    scope: DashboardAccountScope,
    now: datetime | None = None,
) -> dict:
    current_time = now or datetime.now(timezone.utc)
    history_from = current_time - timedelta(days=HISTORY_WINDOW_DAYS)

    current_query = select(WbPriceCurrent).where(WbPriceCurrent.user_id == user_id)
    current_rows = list(
        (
            await session.execute(scope.apply(current_query, WbPriceCurrent.token_id))
        ).scalars().all()
    )

    history_query = (
        select(WbPriceChange)
        .where(
            WbPriceChange.user_id == user_id,
            WbPriceChange.changed_at >= history_from,
        )
        .order_by(WbPriceChange.changed_at.desc(), WbPriceChange.id.desc())
    )
    history_rows = list(
        (
            await session.execute(scope.apply(history_query, WbPriceChange.token_id))
        ).scalars().all()
    )

    product_query = select(WbProduct).where(WbProduct.user_id == user_id)
    product_rows = list(
        (
            await session.execute(scope.apply(product_query, WbProduct.token_id))
        ).scalars().all()
    )
    title_by_key = {
        (row.token_id, row.nm_id): row.title for row in product_rows
    }

    token_query = select(APIToken.id, APIToken.label).where(
        APIToken.user_id == user_id,
        APIToken.id.in_(scope.token_ids),
    )
    token_rows = (await session.execute(token_query)).all()
    account_label_by_id = {
        row.id: (row.label or "Wildberries") for row in token_rows
    }

    history_by_product: dict[tuple[UUID, int], list[WbPriceChange]] = defaultdict(list)
    for change in history_rows:
        history_by_product[(change.token_id, change.nm_id)].append(change)

    current_by_product: dict[tuple[UUID, int], list[WbPriceCurrent]] = defaultdict(list)
    for row in current_rows:
        current_by_product[(row.token_id, row.nm_id)].append(row)

    products: list[dict] = []
    for (token_id, nm_id), rows in current_by_product.items():
        rows.sort(key=lambda row: row.size_id)
        changes = history_by_product.get((token_id, nm_id), [])
        vendor_code = next((row.vendor_code for row in rows if row.vendor_code), None)
        currency = next((row.currency for row in rows if row.currency), None)
        products.append(
            {
                "token_id": str(token_id),
                "account_label": account_label_by_id.get(token_id, "Wildberries"),
                "nm_id": nm_id,
                "product_name": title_by_key.get((token_id, nm_id)),
                "vendor_code": vendor_code,
                "currency": currency,
                "size_count": len(rows),
                "base_price": _range(row.base_price for row in rows),
                "discounted_price": _range(row.discounted_price for row in rows),
                "club_discounted_price": _range(
                    row.club_discounted_price for row in rows
                ),
                "discount": max(float(row.discount or 0) for row in rows),
                "club_discount": max(float(row.club_discount or 0) for row in rows),
                "has_club_price": any(
                    row.club_discounted_price is not None for row in rows
                ),
                "is_bad_turnover": any(row.is_bad_turnover for row in rows),
                "editable_size_price": any(row.editable_size_price for row in rows),
                "observed_at": max(row.observed_at for row in rows).isoformat(),
                "changes_30d": len(changes),
                "last_change_at": (
                    max(change.changed_at for change in changes).isoformat()
                    if changes
                    else None
                ),
            }
        )

    products.sort(
        key=lambda row: (
            -row["changes_30d"],
            not row["is_bad_turnover"],
            row["product_name"] or row["vendor_code"] or str(row["nm_id"]),
        )
    )

    product_discounts = [row["discount"] for row in products]
    changed_products = {
        (row.token_id, row.nm_id) for row in history_rows
    }
    summary = {
        "products": len(products),
        "sizes": len(current_rows),
        "changes_30d": len(history_rows),
        "changed_products_30d": len(changed_products),
        "avg_discount": (
            round(sum(product_discounts) / len(product_discounts), 2)
            if product_discounts
            else 0.0
        ),
        "club_price_products": sum(row["has_club_price"] for row in products),
        "bad_turnover_products": sum(row["is_bad_turnover"] for row in products),
    }

    recent_changes = [
        _serialize_change(
            row,
            title=title_by_key.get((row.token_id, row.nm_id)),
            account_label=account_label_by_id.get(row.token_id, "Wildberries"),
        )
        for row in history_rows[:RECENT_CHANGE_LIMIT]
    ]

    return {
        "summary": summary,
        "products": products,
        "recent_changes": recent_changes,
        "history_window_days": HISTORY_WINDOW_DAYS,
    }
