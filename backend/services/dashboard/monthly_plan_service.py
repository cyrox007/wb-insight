from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.monthly_revenue_plan import MonthlyRevenuePlan
from services.dashboard.account_scope import DashboardAccountScope


@dataclass(frozen=True)
class MonthlyPlanSummary:
    revenue_target: float | None
    configured_accounts: int
    total_accounts: int

    @property
    def complete(self) -> bool:
        return self.total_accounts > 0 and self.configured_accounts == self.total_accounts


@dataclass(frozen=True)
class MonthlyPlanMetrics:
    fact_revenue: float
    revenue_target: float | None
    done_percent: float | None
    forecast_revenue: float
    required_revenue_per_day: float | None
    required_orders_per_day: float | None
    days_in_month: int
    elapsed_days: int
    remaining_days: int


def normalize_month(value: date) -> date:
    return value.replace(day=1)


def calculate_monthly_plan_metrics(
    *,
    fact_revenue: float,
    revenue_target: float | None,
    ordered_amount: float,
    ordered_count: int,
    today: date,
) -> MonthlyPlanMetrics:
    days_in_month = monthrange(today.year, today.month)[1]
    elapsed_days = today.day
    remaining_days = max(0, days_in_month - elapsed_days)
    forecast = (
        fact_revenue / elapsed_days * days_in_month
        if elapsed_days > 0
        else fact_revenue
    )

    done_percent: float | None = None
    required_revenue_per_day: float | None = None
    required_orders_per_day: float | None = None

    if revenue_target is not None and revenue_target > 0:
        done_percent = fact_revenue / revenue_target * 100
        gap = max(0.0, revenue_target - fact_revenue)
        if gap == 0:
            required_revenue_per_day = 0.0
            required_orders_per_day = 0.0
        elif remaining_days > 0:
            required_revenue_per_day = gap / remaining_days
            avg_order_value = (
                ordered_amount / ordered_count if ordered_count > 0 else 0.0
            )
            if avg_order_value > 0:
                required_orders_per_day = required_revenue_per_day / avg_order_value

    return MonthlyPlanMetrics(
        fact_revenue=round(fact_revenue, 2),
        revenue_target=(
            round(revenue_target, 2) if revenue_target is not None else None
        ),
        done_percent=(round(done_percent, 2) if done_percent is not None else None),
        forecast_revenue=round(forecast, 2),
        required_revenue_per_day=(
            round(required_revenue_per_day, 2)
            if required_revenue_per_day is not None
            else None
        ),
        required_orders_per_day=(
            round(required_orders_per_day, 2)
            if required_orders_per_day is not None
            else None
        ),
        days_in_month=days_in_month,
        elapsed_days=elapsed_days,
        remaining_days=remaining_days,
    )


async def get_monthly_plan_summary(
    session: AsyncSession,
    user_id: UUID,
    month: date,
    scope: DashboardAccountScope,
) -> MonthlyPlanSummary:
    month = normalize_month(month)
    query = select(
        func.sum(MonthlyRevenuePlan.revenue_target).label("revenue_target"),
        func.count(MonthlyRevenuePlan.id).label("configured_accounts"),
    ).where(
        MonthlyRevenuePlan.user_id == user_id,
        MonthlyRevenuePlan.month == month,
    )
    query = scope.apply(query, MonthlyRevenuePlan.token_id)
    row = (await session.execute(query)).one()
    configured = int(row.configured_accounts or 0)
    return MonthlyPlanSummary(
        revenue_target=(
            float(row.revenue_target) if configured > 0 and row.revenue_target is not None else None
        ),
        configured_accounts=configured,
        total_accounts=len(scope.token_ids),
    )


async def upsert_monthly_revenue_plan(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    month: date,
    revenue_target: Decimal,
) -> None:
    month = normalize_month(month)
    now = datetime.now(timezone.utc)
    stmt = insert(MonthlyRevenuePlan).values(
        user_id=user_id,
        token_id=token_id,
        month=month,
        revenue_target=revenue_target,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_monthly_revenue_plan_user_token_month",
        set_={
            "revenue_target": stmt.excluded.revenue_target,
            "updated_at": now,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def delete_monthly_revenue_plan(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    month: date,
) -> int:
    stmt = delete(MonthlyRevenuePlan).where(
        MonthlyRevenuePlan.user_id == user_id,
        MonthlyRevenuePlan.token_id == token_id,
        MonthlyRevenuePlan.month == normalize_month(month),
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)
