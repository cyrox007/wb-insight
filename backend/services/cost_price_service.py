from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_cost_price_history import ProductCostPriceHistory
from models.product_cost_price_model import ProductCostPrice
from models.wb_report import WbRealizationReport


async def get_or_cost_price(
    session: AsyncSession,
    user_id: UUID,
    nm_id: int,
) -> Optional[ProductCostPrice]:
    query = select(ProductCostPrice).where(
        ProductCostPrice.user_id == user_id,
        ProductCostPrice.nm_id == nm_id,
    )
    return (await session.execute(query)).scalar_one_or_none()


def _parse_effective_from(value) -> date:
    if value in (None, ""):
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_cost(value) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Некорректная себестоимость") from exc
    if parsed < 0:
        raise ValueError("Себестоимость не может быть отрицательной")
    return parsed.quantize(Decimal("0.01"))


async def upsert_cost_prices(
    session: AsyncSession,
    user_id: UUID,
    items: list[dict],
) -> int:
    """Write date-effective COGS versions and keep a latest-value snapshot.

    Re-uploading the same SKU/effective date is treated as a correction of that
    version. Back-dated corrections never overwrite a newer current snapshot.
    """
    normalized: list[dict] = []
    now = datetime.now(timezone.utc)

    for item in items:
        nm_id = int(item.get("nm_id") or 0)
        if nm_id <= 0:
            raise ValueError("Артикул WB должен быть положительным")
        normalized.append(
            {
                "user_id": user_id,
                "nm_id": nm_id,
                "seller_sku": item.get("seller_sku"),
                "product_name": item.get("product_name"),
                "cost_price": _parse_cost(item.get("cost_price", 0)),
                "currency": str(item.get("currency") or "RUB").upper(),
                "comment": item.get("comment"),
                "effective_from": _parse_effective_from(item.get("effective_from")),
                "created_at": now,
                "updated_at": now,
            }
        )

    if not normalized:
        return 0

    history_stmt = insert(ProductCostPriceHistory).values(normalized)
    history_stmt = history_stmt.on_conflict_do_update(
        constraint="uq_product_cost_history_user_nm_effective",
        set_={
            "seller_sku": history_stmt.excluded.seller_sku,
            "product_name": history_stmt.excluded.product_name,
            "cost_price": history_stmt.excluded.cost_price,
            "currency": history_stmt.excluded.currency,
            "comment": history_stmt.excluded.comment,
            "updated_at": history_stmt.excluded.updated_at,
        },
    )
    await session.execute(history_stmt)

    # Resolve the actual latest version after all corrections/backfills and use
    # it as the compatibility snapshot consumed by existing forms/list views.
    nm_ids = sorted({row["nm_id"] for row in normalized})
    latest_dates = (
        select(
            ProductCostPriceHistory.nm_id.label("nm_id"),
            func.max(ProductCostPriceHistory.effective_from).label("effective_from"),
        )
        .where(
            ProductCostPriceHistory.user_id == user_id,
            ProductCostPriceHistory.nm_id.in_(nm_ids),
        )
        .group_by(ProductCostPriceHistory.nm_id)
        .subquery()
    )
    latest_rows = (
        await session.execute(
            select(ProductCostPriceHistory)
            .join(
                latest_dates,
                and_(
                    latest_dates.c.nm_id == ProductCostPriceHistory.nm_id,
                    latest_dates.c.effective_from
                    == ProductCostPriceHistory.effective_from,
                ),
            )
            .where(ProductCostPriceHistory.user_id == user_id)
        )
    ).scalars().all()

    snapshots = [
        {
            "user_id": row.user_id,
            "nm_id": row.nm_id,
            "seller_sku": row.seller_sku,
            "product_name": row.product_name,
            "cost_price": row.cost_price,
            "currency": row.currency,
            "comment": row.comment,
            "effective_from": row.effective_from,
            "created_at": now,
            "updated_at": now,
        }
        for row in latest_rows
    ]
    if snapshots:
        snapshot_stmt = insert(ProductCostPrice).values(snapshots)
        snapshot_stmt = snapshot_stmt.on_conflict_do_update(
            constraint="uq_user_nm_cost_price",
            set_={
                "seller_sku": snapshot_stmt.excluded.seller_sku,
                "product_name": snapshot_stmt.excluded.product_name,
                "cost_price": snapshot_stmt.excluded.cost_price,
                "currency": snapshot_stmt.excluded.currency,
                "comment": snapshot_stmt.excluded.comment,
                "effective_from": snapshot_stmt.excluded.effective_from,
                "updated_at": snapshot_stmt.excluded.updated_at,
            },
        )
        await session.execute(snapshot_stmt)

    return len(normalized)


def _effective_cost_scalar(user_id: UUID):
    history = ProductCostPriceHistory
    return (
        select(history.cost_price)
        .where(
            history.user_id == user_id,
            history.nm_id == WbRealizationReport.nm_id,
            history.effective_from <= WbRealizationReport.rr_dt,
        )
        .order_by(history.effective_from.desc())
        .limit(1)
        .correlate(WbRealizationReport)
        .scalar_subquery()
    )


async def calculate_unit_economy(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    nm_id: Optional[int] = None,
) -> Optional[dict]:
    conditions = [
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name.in_(["Продажа", "Возврат"]),
    ]
    if nm_id:
        conditions.append(WbRealizationReport.nm_id == nm_id)

    base_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("revenue"),
                func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("payout"),
                func.coalesce(func.sum(WbRealizationReport.ppvz_sales_commission), 0).label("commission"),
                func.coalesce(func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub), 0).label("logistics"),
                func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
                func.coalesce(func.sum(WbRealizationReport.storage_fee), 0).label("storage"),
            ).where(*conditions)
        )
    ).one()

    revenue = float(base_row.revenue or 0)
    if revenue == 0:
        return None

    effective_cost = func.coalesce(_effective_cost_scalar(user_id), 0)
    signed_qty = case(
        (WbRealizationReport.supplier_oper_name == "Возврат", -WbRealizationReport.quantity),
        else_=WbRealizationReport.quantity,
    )
    total_cost = float(
        (
            await session.execute(
                select(func.coalesce(func.sum(signed_qty * effective_cost), 0)).where(
                    *conditions
                )
            )
        ).scalar_one()
        or 0
    )

    payout = float(base_row.payout or 0)
    commission = float(base_row.commission or 0)
    logistics = float(base_row.logistics or 0)
    penalty = float(base_row.penalty or 0)
    storage = float(base_row.storage or 0)
    profit = payout - total_cost
    margin_percent = profit / revenue * 100 if revenue > 0 else 0.0
    drr_percent = (commission + logistics + penalty) / revenue * 100 if revenue > 0 else 0.0
    profitability_percent = profit / payout * 100 if payout > 0 else 0.0

    return {
        "revenue": round(revenue, 2),
        "total_cost": round(total_cost, 2),
        "payout": round(payout, 2),
        "commission": round(commission, 2),
        "logistics": round(logistics, 2),
        "penalty": round(penalty, 2),
        "storage": round(storage, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin_percent, 2),
        "drr_percent": round(drr_percent, 2),
        "profitability_percent": round(profitability_percent, 2),
    }


async def get_dashboard_unit_economy(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> dict:
    metrics = await calculate_unit_economy(session, user_id, start_date, end_date)
    if not metrics:
        return {
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "total_profit": 0.0,
            "avg_margin_percent": 0.0,
            "avg_drr_percent": 0.0,
            "products_with_cost": 0,
            "products_without_cost": 0,
        }

    cost_exists = exists().where(
        ProductCostPriceHistory.user_id == user_id,
        ProductCostPriceHistory.nm_id == WbRealizationReport.nm_id,
        ProductCostPriceHistory.effective_from <= end_date,
    )
    coverage = (
        await session.execute(
            select(
                func.count(func.distinct(WbRealizationReport.nm_id)).label("total"),
                func.count(
                    func.distinct(
                        case((cost_exists, WbRealizationReport.nm_id), else_=None)
                    )
                ).label("with_cost"),
            ).where(
                WbRealizationReport.user_id == user_id,
                WbRealizationReport.rr_dt >= start_date,
                WbRealizationReport.rr_dt <= end_date,
            )
        )
    ).one()

    with_cost = int(coverage.with_cost or 0)
    total = int(coverage.total or 0)
    return {
        "total_revenue": metrics["revenue"],
        "total_cost": metrics["total_cost"],
        "total_profit": metrics["profit"],
        "avg_margin_percent": metrics["margin_percent"],
        "avg_drr_percent": metrics["drr_percent"],
        "products_with_cost": with_cost,
        "products_without_cost": max(0, total - with_cost),
    }


async def get_product_list_with_costs(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    rows = (
        await session.execute(
            select(
                WbRealizationReport.nm_id,
                func.max(WbRealizationReport.sa_name).label("seller_sku"),
                func.max(WbRealizationReport.brand_name).label("brand"),
                func.max(WbRealizationReport.title).label("product_name"),
                func.sum(WbRealizationReport.retail_amount).label("revenue"),
                func.sum(WbRealizationReport.quantity).label("quantity"),
                func.sum(WbRealizationReport.ppvz_for_pay).label("payout"),
                func.sum(WbRealizationReport.ppvz_sales_commission).label("commission"),
                func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub).label("logistics"),
                func.sum(WbRealizationReport.penalty).label("penalty"),
            )
            .where(
                WbRealizationReport.user_id == user_id,
                WbRealizationReport.rr_dt >= start_date,
                WbRealizationReport.rr_dt <= end_date,
                WbRealizationReport.supplier_oper_name.in_(["Продажа", "Возврат"]),
            )
            .group_by(WbRealizationReport.nm_id)
            .order_by(func.sum(WbRealizationReport.retail_amount).desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    products: list[dict] = []
    for row in rows:
        item_metrics = await calculate_unit_economy(
            session,
            user_id,
            start_date,
            end_date,
            nm_id=row.nm_id,
        )
        current = await get_or_cost_price(session, user_id, row.nm_id)
        metrics = item_metrics or {}
        products.append(
            {
                "nm_id": row.nm_id,
                "seller_sku": row.seller_sku,
                "brand": row.brand,
                "product_name": row.product_name,
                "revenue": round(float(row.revenue or 0), 2),
                "quantity": int(row.quantity or 0),
                "cost_price": float(current.cost_price) if current else 0.0,
                "cost_effective_from": current.effective_from if current else None,
                "total_cost": metrics.get("total_cost", 0.0),
                "payout": metrics.get("payout", 0.0),
                "profit": metrics.get("profit", 0.0),
                "margin_percent": metrics.get("margin_percent", 0.0),
                "drr_percent": metrics.get("drr_percent", 0.0),
                "has_cost": current is not None,
            }
        )

    total_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(WbRealizationReport.nm_id))).where(
                    WbRealizationReport.user_id == user_id,
                    WbRealizationReport.rr_dt >= start_date,
                    WbRealizationReport.rr_dt <= end_date,
                )
            )
        ).scalar_one()
        or 0
    )
    return products, total_count
