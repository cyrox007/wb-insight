from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_cost_price_model import ProductCostPrice
from models.wb_report import WbRealizationReport


async def get_reports_with_costs_scoped(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    token_id: UUID | None = None,
) -> list[tuple[WbRealizationReport, Optional[ProductCostPrice]]]:
    conditions = [
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= date_from,
        WbRealizationReport.rr_dt <= date_to,
    ]
    if token_id is not None:
        conditions.append(WbRealizationReport.token_id == token_id)

    stmt = (
        select(WbRealizationReport, ProductCostPrice)
        .outerjoin(
            ProductCostPrice,
            and_(
                WbRealizationReport.nm_id == ProductCostPrice.nm_id,
                ProductCostPrice.user_id == user_id,
            ),
        )
        .where(*conditions)
        .order_by(
            WbRealizationReport.nm_id.asc(),
            WbRealizationReport.rr_dt.asc(),
        )
    )
    rows = (await session.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]
