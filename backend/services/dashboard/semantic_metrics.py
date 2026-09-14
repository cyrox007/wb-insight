from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from models.wb_advertising_stats import WbAdvertisingStats
from models.wb_operational import WbOrder
from services.dashboard.account_scope import DashboardAccountScope


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class OrderTotals:
    count: int = 0
    amount: float = 0.0
    canceled_count: int = 0


@dataclass(frozen=True)
class AdvertisingTotals:
    views: int = 0
    clicks: int = 0
    added_to_cart: int = 0
    orders: int = 0
    orders_amount: float = 0.0
    spend: float = 0.0


def inclusive_days(start_date: date, end_date: date) -> int:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    return (end_date - start_date).days + 1


def previous_period(start_date: date, end_date: date) -> tuple[date, date]:
    days = inclusive_days(start_date, end_date)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return previous_start, previous_end


def is_auth_sync_error(error: str | None) -> bool:
    if not error:
        return False
    normalized = error.lower()
    return (
        "401" in normalized
        or "unauthorized" in normalized
        or "ошибка авторизации" in normalized
        or "подключение недействительно" in normalized
    )


def _moscow_period_utc(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    inclusive_days(start_date, end_date)
    start = datetime.combine(start_date, time.min, tzinfo=MOSCOW_TZ).astimezone(
        timezone.utc
    )
    end_exclusive = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=MOSCOW_TZ
    ).astimezone(timezone.utc)
    return start, end_exclusive


async def has_active_sync_jobs(
    session: AsyncSession,
    user_id: UUID,
    scope: DashboardAccountScope,
) -> bool:
    query = select(func.count(SyncJob.id)).where(
        SyncJob.user_id == user_id,
        SyncJob.is_active.is_(True),
    )
    query = scope.apply(query, SyncJob.token_id)
    return bool((await session.execute(query)).scalar() or 0)


async def get_order_totals(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> OrderTotals:
    start, end_exclusive = _moscow_period_utc(start_date, end_date)
    query = select(
        func.count(WbOrder.id).label("order_count"),
        func.coalesce(func.sum(WbOrder.price_with_disc), Decimal("0")).label(
            "order_amount"
        ),
        func.coalesce(
            func.sum(case((WbOrder.is_cancel.is_(True), 1), else_=0)), 0
        ).label("canceled_count"),
    ).where(
        WbOrder.user_id == user_id,
        WbOrder.order_date >= start,
        WbOrder.order_date < end_exclusive,
    )
    query = scope.apply(query, WbOrder.token_id)
    row = (await session.execute(query)).one()
    return OrderTotals(
        count=int(row.order_count or 0),
        amount=float(row.order_amount or 0),
        canceled_count=int(row.canceled_count or 0),
    )


async def get_order_totals_by_nm(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> dict[int, OrderTotals]:
    start, end_exclusive = _moscow_period_utc(start_date, end_date)
    query = (
        select(
            WbOrder.nm_id.label("nm_id"),
            func.count(WbOrder.id).label("order_count"),
            func.coalesce(func.sum(WbOrder.price_with_disc), Decimal("0")).label(
                "order_amount"
            ),
            func.coalesce(
                func.sum(case((WbOrder.is_cancel.is_(True), 1), else_=0)), 0
            ).label("canceled_count"),
        )
        .where(
            WbOrder.user_id == user_id,
            WbOrder.nm_id.is_not(None),
            WbOrder.order_date >= start,
            WbOrder.order_date < end_exclusive,
        )
        .group_by(WbOrder.nm_id)
    )
    query = scope.apply(query, WbOrder.token_id)
    rows = (await session.execute(query)).all()
    return {
        int(row.nm_id): OrderTotals(
            count=int(row.order_count or 0),
            amount=float(row.order_amount or 0),
            canceled_count=int(row.canceled_count or 0),
        )
        for row in rows
        if row.nm_id is not None
    }


async def get_advertising_totals(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> AdvertisingTotals:
    query = select(
        func.coalesce(func.sum(WbAdvertisingStats.views), 0).label("views"),
        func.coalesce(func.sum(WbAdvertisingStats.clicks), 0).label("clicks"),
        func.coalesce(func.sum(WbAdvertisingStats.added_to_cart), 0).label(
            "added_to_cart"
        ),
        func.coalesce(func.sum(WbAdvertisingStats.orders), 0).label("orders"),
        func.coalesce(
            func.sum(WbAdvertisingStats.orders_amount), Decimal("0")
        ).label("orders_amount"),
        func.coalesce(func.sum(WbAdvertisingStats.amount), Decimal("0")).label(
            "spend"
        ),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date,
    )
    query = scope.apply(query, WbAdvertisingStats.token_id)
    row = (await session.execute(query)).one()
    return AdvertisingTotals(
        views=int(row.views or 0),
        clicks=int(row.clicks or 0),
        added_to_cart=int(row.added_to_cart or 0),
        orders=int(row.orders or 0),
        orders_amount=float(row.orders_amount or 0),
        spend=float(row.spend or 0),
    )


async def get_advertising_spend_by_nm(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> dict[int, float]:
    """Return actual advertising spend grouped by WB article for Unit Economy."""
    query = (
        select(
            WbAdvertisingStats.nm_id.label("nm_id"),
            func.coalesce(func.sum(WbAdvertisingStats.amount), Decimal("0")).label(
                "spend"
            ),
        )
        .where(
            WbAdvertisingStats.user_id == user_id,
            WbAdvertisingStats.nm_id.is_not(None),
            WbAdvertisingStats.date >= start_date,
            WbAdvertisingStats.date <= end_date,
        )
        .group_by(WbAdvertisingStats.nm_id)
    )
    query = scope.apply(query, WbAdvertisingStats.token_id)
    rows = (await session.execute(query)).all()
    return {
        int(row.nm_id): float(row.spend or 0)
        for row in rows
        if row.nm_id is not None
    }
