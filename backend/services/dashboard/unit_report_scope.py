from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models.product_cost_price_history import ProductCostPriceHistory
from models.wb_report import WbRealizationReport
from services.dashboard.account_scope import DashboardAccountScope


async def get_reports_with_costs_scoped(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    scope: DashboardAccountScope,
) -> list[tuple[WbRealizationReport, Optional[ProductCostPriceHistory]]]:
    """Load finance rows with the cost version effective on each report date."""
    history = aliased(ProductCostPriceHistory)
    effective_from = (
        select(func.max(ProductCostPriceHistory.effective_from))
        .where(
            ProductCostPriceHistory.user_id == user_id,
            ProductCostPriceHistory.nm_id == WbRealizationReport.nm_id,
            ProductCostPriceHistory.effective_from <= WbRealizationReport.rr_dt,
        )
        .correlate(WbRealizationReport)
        .scalar_subquery()
    )

    stmt = (
        select(WbRealizationReport, history)
        .outerjoin(
            history,
            and_(
                history.user_id == user_id,
                history.nm_id == WbRealizationReport.nm_id,
                history.effective_from == effective_from,
            ),
        )
        .where(
            WbRealizationReport.user_id == user_id,
            WbRealizationReport.rr_dt >= date_from,
            WbRealizationReport.rr_dt <= date_to,
        )
        .order_by(
            WbRealizationReport.nm_id.asc(),
            WbRealizationReport.rr_dt.asc(),
        )
    )
    stmt = scope.apply(stmt, WbRealizationReport.token_id)
    rows = (await session.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]
