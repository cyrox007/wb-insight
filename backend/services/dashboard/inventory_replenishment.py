from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_operational import WbOrder
from models.wb_product import WbProduct
from models.wb_stock import WbStock
from services.dashboard.account_scope import DashboardAccountScope


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_CRITICAL_DAYS = 14
DEFAULT_TARGET_DAYS = 30


@dataclass(frozen=True)
class InventoryRecommendation:
    nm_id: int
    product_name: str | None
    stock_units: int
    in_way_to_client: int
    in_way_from_client: int
    orders_30d: int
    orders_per_day: float
    coverage_days: float | None
    recommended_supply_units: int
    excess_units: int
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InventorySummary:
    products: int
    stock_units: int
    in_way_to_client: int
    in_way_from_client: int
    critical_products: int
    replenish_products: int
    no_demand_products: int
    recommended_supply_units: int

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_inventory_recommendation(
    *,
    nm_id: int,
    stock_units: int,
    orders_count: int,
    product_name: str | None = None,
    in_way_to_client: int = 0,
    in_way_from_client: int = 0,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    critical_days: int = DEFAULT_CRITICAL_DAYS,
    target_days: int = DEFAULT_TARGET_DAYS,
) -> InventoryRecommendation:
    """Apply the replenishment semantics from the source WB workbook.

    Demand velocity is based on non-cancelled orders from completed days.
    Transit quantities are deliberately shown separately and do not increase FBO
    coverage, matching the workbook formula.
    """
    if lookback_days <= 0:
        raise ValueError("lookback_days должен быть больше нуля")
    if critical_days < 0:
        raise ValueError("critical_days не может быть отрицательным")
    if target_days <= 0:
        raise ValueError("target_days должен быть больше нуля")
    if target_days < critical_days:
        raise ValueError("target_days не может быть меньше critical_days")

    stock = max(int(stock_units or 0), 0)
    orders = max(int(orders_count or 0), 0)
    daily_orders = orders / lookback_days

    if daily_orders > 0:
        coverage = stock / daily_orders
        target_units = daily_orders * target_days
        recommended = max(ceil(target_units - stock), 0)
        excess = max(ceil(stock - target_units), 0)

        if stock == 0:
            status = "out_of_stock"
        elif coverage < critical_days:
            status = "critical"
        elif coverage < target_days:
            status = "replenish"
        else:
            status = "healthy"
    else:
        coverage = None
        recommended = 0
        excess = stock
        status = "no_demand" if stock > 0 else "no_stock_no_demand"

    return InventoryRecommendation(
        nm_id=nm_id,
        product_name=product_name,
        stock_units=stock,
        in_way_to_client=max(int(in_way_to_client or 0), 0),
        in_way_from_client=max(int(in_way_from_client or 0), 0),
        orders_30d=orders,
        orders_per_day=round(daily_orders, 2),
        coverage_days=None if coverage is None else round(coverage, 1),
        recommended_supply_units=recommended,
        excess_units=excess,
        status=status,
    )


def _completed_period_bounds(
    today: date,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[date, date, datetime, datetime]:
    start_date = today - timedelta(days=lookback_days)
    end_date = today - timedelta(days=1)
    start_local = datetime.combine(start_date, time.min, tzinfo=MOSCOW_TZ)
    end_exclusive_local = datetime.combine(today, time.min, tzinfo=MOSCOW_TZ)
    return (
        start_date,
        end_date,
        start_local.astimezone(timezone.utc),
        end_exclusive_local.astimezone(timezone.utc),
    )


async def get_inventory_replenishment(
    session: AsyncSession,
    *,
    user_id: UUID,
    scope: DashboardAccountScope,
    today: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    critical_days: int = DEFAULT_CRITICAL_DAYS,
    target_days: int = DEFAULT_TARGET_DAYS,
) -> dict:
    today = today or datetime.now(MOSCOW_TZ).date()
    period_start, period_end, start_dt, end_exclusive_dt = _completed_period_bounds(
        today,
        lookback_days=lookback_days,
    )

    stock_query = (
        select(
            WbStock.nm_id,
            func.sum(WbStock.quantity).label("stock_units"),
            func.sum(WbStock.in_way_to_client).label("in_way_to_client"),
            func.sum(WbStock.in_way_from_client).label("in_way_from_client"),
        )
        .where(WbStock.user_id == user_id, WbStock.nm_id.is_not(None))
        .group_by(WbStock.nm_id)
    )
    stock_rows = (
        await session.execute(scope.apply(stock_query, WbStock.token_id))
    ).all()

    order_query = (
        select(
            WbOrder.nm_id,
            func.count(WbOrder.id).label("orders_count"),
        )
        .where(
            WbOrder.user_id == user_id,
            WbOrder.nm_id.is_not(None),
            WbOrder.is_cancel.is_(False),
            WbOrder.order_date >= start_dt,
            WbOrder.order_date < end_exclusive_dt,
        )
        .group_by(WbOrder.nm_id)
    )
    order_rows = (
        await session.execute(scope.apply(order_query, WbOrder.token_id))
    ).all()

    product_query = (
        select(WbProduct.nm_id, func.max(WbProduct.title).label("title"))
        .where(WbProduct.user_id == user_id)
        .group_by(WbProduct.nm_id)
    )
    product_rows = (
        await session.execute(scope.apply(product_query, WbProduct.token_id))
    ).all()

    stock_by_nm = {
        int(row.nm_id): {
            "stock_units": int(row.stock_units or 0),
            "in_way_to_client": int(row.in_way_to_client or 0),
            "in_way_from_client": int(row.in_way_from_client or 0),
        }
        for row in stock_rows
        if row.nm_id is not None
    }
    orders_by_nm = {
        int(row.nm_id): int(row.orders_count or 0)
        for row in order_rows
        if row.nm_id is not None
    }
    titles_by_nm = {
        int(row.nm_id): row.title
        for row in product_rows
        if row.nm_id is not None
    }

    nm_ids = set(stock_by_nm) | set(orders_by_nm)
    items = []
    for nm_id in nm_ids:
        stock = stock_by_nm.get(nm_id, {})
        items.append(
            calculate_inventory_recommendation(
                nm_id=nm_id,
                product_name=titles_by_nm.get(nm_id),
                stock_units=stock.get("stock_units", 0),
                in_way_to_client=stock.get("in_way_to_client", 0),
                in_way_from_client=stock.get("in_way_from_client", 0),
                orders_count=orders_by_nm.get(nm_id, 0),
                lookback_days=lookback_days,
                critical_days=critical_days,
                target_days=target_days,
            )
        )

    status_rank = {
        "out_of_stock": 0,
        "critical": 1,
        "replenish": 2,
        "healthy": 3,
        "no_demand": 4,
        "no_stock_no_demand": 5,
    }
    items.sort(
        key=lambda item: (
            status_rank.get(item.status, 99),
            item.coverage_days if item.coverage_days is not None else float("inf"),
            -item.orders_per_day,
            item.nm_id,
        )
    )

    summary = InventorySummary(
        products=len(items),
        stock_units=sum(item.stock_units for item in items),
        in_way_to_client=sum(item.in_way_to_client for item in items),
        in_way_from_client=sum(item.in_way_from_client for item in items),
        critical_products=sum(
            item.status in {"out_of_stock", "critical"} for item in items
        ),
        replenish_products=sum(
            item.status in {"out_of_stock", "critical", "replenish"}
            for item in items
        ),
        no_demand_products=sum(item.status == "no_demand" for item in items),
        recommended_supply_units=sum(
            item.recommended_supply_units for item in items
        ),
    )

    return {
        "summary": summary.to_dict(),
        "items": [item.to_dict() for item in items],
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "lookback_days": lookback_days,
            "critical_days": critical_days,
            "target_days": target_days,
        },
    }
