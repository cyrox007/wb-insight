from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from services.dashboard.account_scope import DashboardAccountScope
from services.dashboard.financial_semantics import calculate_financial_metrics_scoped


async def get_dashboard_unit_economy_scoped(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> dict:
    """Возвращает тот же финансовый итог, который использует юнит-экономика."""
    result = await calculate_financial_metrics_scoped(
        session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    if result.metrics.empty:
        return {
            "sales_without_spp": 0.0,
            "sales_with_spp": 0.0,
            "sales_quantity": 0,
            "returns_amount": 0.0,
            "ppvz_for_pay": 0.0,
            "logistics": 0.0,
            "storage": 0.0,
            "total_cost": 0.0,
            "other_expenses": 0.0,
            "total_profit": 0.0,
            "avg_margin_percent": 0.0,
            "avg_drr_percent": 0.0,
            "profit_complete": result.profit_complete,
            "cost_coverage_percent": result.cost_coverage_percent,
            "cost_missing_operations": result.cost_missing_operations,
            "products_with_cost": result.products_with_cost,
            "products_without_cost": result.products_without_cost,
        }

    summary = result.metrics.iloc[0]
    return {
        "sales_without_spp": float(summary.get("sales_without_spp", 0) or 0),
        "sales_with_spp": float(summary.get("sales_with_spp", 0) or 0),
        "sales_quantity": int(summary.get("sales_quantity", 0) or 0),
        "returns_amount": float(summary.get("returns_amount", 0) or 0),
        "ppvz_for_pay": float(summary.get("ppvz_for_pay", 0) or 0),
        "logistics": float(summary.get("delivery_rub", 0) or 0),
        "storage": float(summary.get("storage_fee", 0) or 0),
        "total_cost": float(summary.get("product_cost", 0) or 0),
        "other_expenses": float(summary.get("other_expenses", 0) or 0),
        "total_profit": float(summary.get("profit", 0) or 0),
        "avg_margin_percent": float(summary.get("margin", 0) or 0),
        "avg_drr_percent": float(summary.get("drr", 0) or 0),
        "profit_complete": result.profit_complete,
        "cost_coverage_percent": result.cost_coverage_percent,
        "cost_missing_operations": result.cost_missing_operations,
        "products_with_cost": result.products_with_cost,
        "products_without_cost": result.products_without_cost,
    }
