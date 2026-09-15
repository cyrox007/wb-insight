from datetime import date
from uuid import UUID

from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_cost_price_history import ProductCostPriceHistory
from models.wb_report import WbRealizationReport
from services.dashboard.account_scope import DashboardAccountScope
from services.manual_expense_service import get_manual_expense_totals


def _effective_cost_scalar(user_id: UUID):
    return (
        select(ProductCostPriceHistory.cost_price)
        .where(
            ProductCostPriceHistory.user_id == user_id,
            ProductCostPriceHistory.nm_id == WbRealizationReport.nm_id,
            ProductCostPriceHistory.effective_from <= WbRealizationReport.rr_dt,
        )
        .order_by(ProductCostPriceHistory.effective_from.desc())
        .limit(1)
        .correlate(WbRealizationReport)
        .scalar_subquery()
    )


async def get_dashboard_unit_economy_scoped(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> dict:
    conditions = [
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name.in_(["Продажа", "Возврат"]),
    ]

    base_query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("revenue"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("payout"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_sales_commission), 0).label("commission"),
        func.coalesce(func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub), 0).label("logistics"),
        func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
    ).where(*conditions)
    base_query = scope.apply(base_query, WbRealizationReport.token_id)
    row = (await session.execute(base_query)).one()

    revenue = float(row.revenue or 0)
    payout = float(row.payout or 0)
    commission = float(row.commission or 0)
    logistics = float(row.logistics or 0)
    penalty = float(row.penalty or 0)

    effective_cost = func.coalesce(_effective_cost_scalar(user_id), 0)
    signed_qty = case(
        (WbRealizationReport.supplier_oper_name == "Возврат", -WbRealizationReport.quantity),
        else_=WbRealizationReport.quantity,
    )
    cost_query = select(
        func.coalesce(func.sum(signed_qty * effective_cost), 0).label("total_cost")
    ).where(*conditions)
    cost_query = scope.apply(cost_query, WbRealizationReport.token_id)
    total_cost = float((await session.execute(cost_query)).scalar_one() or 0)

    other_expenses, _ = await get_manual_expense_totals(
        session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    profit = payout - total_cost - other_expenses
    margin = profit / revenue * 100 if revenue > 0 else 0.0
    drr = (commission + logistics + penalty) / revenue * 100 if revenue > 0 else 0.0

    cost_exists = exists().where(
        ProductCostPriceHistory.user_id == user_id,
        ProductCostPriceHistory.nm_id == WbRealizationReport.nm_id,
        ProductCostPriceHistory.effective_from <= end_date,
    )
    coverage_query = select(
        func.count(func.distinct(WbRealizationReport.nm_id)).label("total"),
        func.count(
            func.distinct(
                case((cost_exists, WbRealizationReport.nm_id), else_=None)
            )
        ).label("with_cost"),
    ).where(*conditions)
    coverage_query = scope.apply(coverage_query, WbRealizationReport.token_id)
    coverage = (await session.execute(coverage_query)).one()
    total_products = int(coverage.total or 0)
    with_cost = int(coverage.with_cost or 0)

    return {
        "total_revenue": round(revenue, 2),
        "total_cost": round(total_cost, 2),
        "other_expenses": round(other_expenses, 2),
        "total_profit": round(profit, 2),
        "avg_margin_percent": round(margin, 2),
        "avg_drr_percent": round(drr, 2),
        "products_with_cost": with_cost,
        "products_without_cost": max(0, total_products - with_cost),
    }
