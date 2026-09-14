from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_cost_price_model import ProductCostPrice
from models.wb_report import WbRealizationReport


async def get_dashboard_unit_economy_scoped(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    token_id: UUID | None = None,
) -> dict:
    conditions = [
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name.in_(["Продажа", "Возврат"]),
    ]
    if token_id is not None:
        conditions.append(WbRealizationReport.token_id == token_id)

    base_query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("revenue"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("payout"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_sales_commission), 0).label(
            "commission"
        ),
        func.coalesce(
            func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub),
            0,
        ).label("logistics"),
        func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
    ).where(*conditions)
    row = (await session.execute(base_query)).one()

    revenue = float(row.revenue or 0)
    payout = float(row.payout or 0)
    commission = float(row.commission or 0)
    logistics = float(row.logistics or 0)
    penalty = float(row.penalty or 0)

    cost_query = (
        select(
            WbRealizationReport.nm_id,
            func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("qty"),
            ProductCostPrice.cost_price,
        )
        .outerjoin(
            ProductCostPrice,
            (ProductCostPrice.nm_id == WbRealizationReport.nm_id)
            & (ProductCostPrice.user_id == user_id),
        )
        .where(*conditions)
        .group_by(WbRealizationReport.nm_id, ProductCostPrice.cost_price)
    )
    cost_rows = (await session.execute(cost_query)).all()
    total_cost = sum(
        int(item.qty or 0) * float(item.cost_price or 0) for item in cost_rows
    )

    profit = payout - total_cost
    margin = profit / revenue * 100 if revenue > 0 else 0.0
    drr = (commission + logistics + penalty) / revenue * 100 if revenue > 0 else 0.0

    coverage_query = (
        select(
            func.count(func.distinct(WbRealizationReport.nm_id)).label("total"),
            func.count(func.distinct(ProductCostPrice.nm_id)).label("with_cost"),
        )
        .select_from(WbRealizationReport)
        .outerjoin(
            ProductCostPrice,
            (ProductCostPrice.nm_id == WbRealizationReport.nm_id)
            & (ProductCostPrice.user_id == user_id),
        )
        .where(*conditions)
    )
    coverage = (await session.execute(coverage_query)).one()
    total_products = int(coverage.total or 0)
    with_cost = int(coverage.with_cost or 0)

    return {
        "total_revenue": round(revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(profit, 2),
        "avg_margin_percent": round(margin, 2),
        "avg_drr_percent": round(drr, 2),
        "products_with_cost": with_cost,
        "products_without_cost": max(0, total_products - with_cost),
    }
