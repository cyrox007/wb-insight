from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.wb_advertising_stats import WbAdvertisingStats
from services.dashboard.account_scope import (
    DashboardAccountScope,
    DashboardAccountUnavailableError,
    resolve_dashboard_scope,
)
from services.dashboard.semantic_metrics import (
    AdvertisingTotals,
    OrderTotals,
    get_advertising_totals,
    get_order_totals,
    get_order_totals_by_nm,
    is_auth_sync_error,
)
from services.user_sync_state_service import get_user_sync_states
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/ads", tags=["Advertising"])


def _get_funnel_data(advertising: AdvertisingTotals, orders: OrderTotals) -> Dict[str, Any]:
    return {
        "views": advertising.views,
        "clicks": advertising.clicks,
        "added_to_cart": advertising.added_to_cart,
        "ad_orders": advertising.orders,
        "ad_orders_amount": round(advertising.orders_amount, 2),
        "total_orders": orders.count,
        "total_orders_amount": round(orders.amount, 2),
    }


def _get_conversion_data(advertising: AdvertisingTotals) -> Dict[str, Any]:
    ctr = advertising.clicks / advertising.views * 100 if advertising.views else 0.0
    cr_to_cart = advertising.added_to_cart / advertising.clicks * 100 if advertising.clicks else 0.0
    click_to_order = advertising.orders / advertising.clicks * 100 if advertising.clicks else 0.0
    cpc = advertising.spend / advertising.clicks if advertising.clicks else 0.0
    cpm = advertising.spend / advertising.views * 1000 if advertising.views else 0.0
    drr = advertising.spend / advertising.orders_amount * 100 if advertising.orders_amount else 0.0
    return {
        "expenses": round(advertising.spend, 2),
        "ctr": round(ctr, 2),
        "cr_to_cart": round(cr_to_cart, 2),
        "conversion_click_to_order": round(click_to_order, 2),
        "cpc": round(cpc, 2),
        "cpm": round(cpm, 2),
        "drr": round(drr, 2),
    }


def _get_acquisition_cost_data(advertising: AdvertisingTotals, orders: OrderTotals) -> Dict[str, Any]:
    avg_order_value = orders.amount / orders.count if orders.count else 0.0
    norm_drr = 10.0
    return {
        "avg_order_value": round(avg_order_value, 2),
        "cost_per_view": round(advertising.spend / advertising.views, 2) if advertising.views else 0.0,
        "cost_per_click": round(advertising.spend / advertising.clicks, 2) if advertising.clicks else 0.0,
        "cost_per_cart": round(advertising.spend / advertising.added_to_cart, 2) if advertising.added_to_cart else 0.0,
        "cpo": round(advertising.spend / advertising.orders, 2) if advertising.orders else 0.0,
        "norm_drr": norm_drr,
        "max_cpm": round(avg_order_value * norm_drr / 100, 2) if avg_order_value else 0.0,
    }


async def _get_dynamics_chart(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> List[Dict[str, Any]]:
    query = (
        select(
            WbAdvertisingStats.date.label("date"),
            func.sum(WbAdvertisingStats.views).label("views"),
            func.sum(WbAdvertisingStats.clicks).label("clicks"),
            func.sum(WbAdvertisingStats.amount).label("amount"),
            func.sum(WbAdvertisingStats.orders).label("orders"),
            func.sum(WbAdvertisingStats.orders_amount).label("orders_amount"),
        )
        .where(
            WbAdvertisingStats.user_id == user_id,
            WbAdvertisingStats.date >= start_date,
            WbAdvertisingStats.date <= end_date,
        )
        .group_by(WbAdvertisingStats.date)
        .order_by(WbAdvertisingStats.date)
    )
    rows = (await session.execute(scope.apply(query, WbAdvertisingStats.token_id))).all()
    return [{
        "date": row.date.isoformat(),
        "views": int(row.views or 0),
        "clicks": int(row.clicks or 0),
        "amount": float(row.amount or 0),
        "orders": int(row.orders or 0),
        "orders_amount": float(row.orders_amount or 0),
    } for row in rows]


async def _get_promotion_dynamics(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> List[Dict[str, Any]]:
    query = (
        select(
            WbAdvertisingStats.date.label("date"),
            func.sum(WbAdvertisingStats.views).label("views"),
            func.sum(WbAdvertisingStats.clicks).label("clicks"),
            func.sum(WbAdvertisingStats.amount).label("amount"),
        )
        .where(
            WbAdvertisingStats.user_id == user_id,
            WbAdvertisingStats.date >= start_date,
            WbAdvertisingStats.date <= end_date,
        )
        .group_by(WbAdvertisingStats.date)
        .order_by(WbAdvertisingStats.date)
    )
    rows = (await session.execute(scope.apply(query, WbAdvertisingStats.token_id))).all()
    return [{
        "date": row.date.isoformat(),
        "ctr": round(int(row.clicks or 0) / int(row.views or 0) * 100, 2) if row.views else 0.0,
        "cpm": round(float(row.amount or 0) / int(row.views or 0) * 1000, 2) if row.views else 0.0,
        "amount": round(float(row.amount or 0), 2),
    } for row in rows]


async def _get_articles_table(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    orders_by_nm: dict[int, OrderTotals],
    scope: DashboardAccountScope,
) -> List[Dict[str, Any]]:
    query = (
        select(
            WbAdvertisingStats.nm_id.label("nm_id"),
            WbAdvertisingStats.product_name.label("product_name"),
            func.sum(WbAdvertisingStats.views).label("total_views"),
            func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
            func.sum(WbAdvertisingStats.added_to_cart).label("total_atc"),
            func.sum(WbAdvertisingStats.orders).label("ad_orders"),
            func.sum(WbAdvertisingStats.amount).label("total_amount"),
            func.sum(WbAdvertisingStats.orders_amount).label("ad_orders_amount"),
            func.avg(WbAdvertisingStats.ctr).label("avg_ctr"),
            func.avg(WbAdvertisingStats.cr).label("avg_cr"),
            func.avg(WbAdvertisingStats.cpc).label("avg_cpc"),
        )
        .where(
            WbAdvertisingStats.user_id == user_id,
            WbAdvertisingStats.date >= start_date,
            WbAdvertisingStats.date <= end_date,
        )
        .group_by(WbAdvertisingStats.nm_id, WbAdvertisingStats.product_name)
        .order_by(func.sum(WbAdvertisingStats.amount).desc())
    )
    rows = (await session.execute(scope.apply(query, WbAdvertisingStats.token_id))).all()
    data = []
    for row in rows:
        nm_id = int(row.nm_id)
        total_orders = orders_by_nm.get(nm_id, OrderTotals())
        views, clicks, atc = int(row.total_views or 0), int(row.total_clicks or 0), int(row.total_atc or 0)
        ad_orders, spend = int(row.ad_orders or 0), float(row.total_amount or 0)
        data.append({
            "nm_id": nm_id,
            "product_name": row.product_name or "",
            "views": views,
            "clicks": clicks,
            "added_to_cart": atc,
            "ad_orders": ad_orders,
            "ad_orders_amount": round(float(row.ad_orders_amount or 0), 2),
            "total_orders": total_orders.count,
            "total_orders_amount": round(total_orders.amount, 2),
            "expenses": round(spend, 2),
            "ctr": round(float(row.avg_ctr or 0), 2),
            "cr": round(float(row.avg_cr or 0), 2),
            "cart_to_order": round(ad_orders / atc * 100, 2) if atc else 0.0,
            "click_to_order": round(ad_orders / clicks * 100, 2) if clicks else 0.0,
            "cpc": round(float(row.avg_cpc or 0), 2),
            "order_cost_in_ads": round(spend / ad_orders, 2) if ad_orders else 0.0,
            "drr_from_orders": round(spend / total_orders.amount * 100, 2) if total_orders.amount else 0.0,
            "cpm": round(spend / views * 1000, 2) if views else 0.0,
        })
    return data


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_advertising_stats(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    token_id: Optional[UUID] = None,
):
    end_date = end_date or datetime.now(timezone.utc).date()
    start_date = start_date or end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    try:
        scope = await resolve_dashboard_scope(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(code="ACCOUNT_NOT_AVAILABLE", message=str(exc))

    states = await get_user_sync_states(session=db_session, user_id=user_id)
    scoped_states = [state for state in states if scope.contains(state.token_id)]
    sync_errors = [state.last_error for state in scoped_states if state.last_error]
    if not scope.token_ids:
        if any(is_auth_sync_error(error) for error in sync_errors):
            return response_error(message="Ошибка авторизации: подключение недействительно или истекло. Обновите кабинет Wildberries в настройках.", code="TOKEN_INVALID")
        return response_error(message="Нет действительных кабинетов Wildberries, доступных на текущем тарифе.", code="NO_VALID_TOKENS")

    advertising = await get_advertising_totals(db_session, user_id, start_date, end_date, scope)
    orders = await get_order_totals(db_session, user_id, start_date, end_date, scope)
    orders_by_nm = await get_order_totals_by_nm(db_session, user_id, start_date, end_date, scope)
    dynamics_chart = await _get_dynamics_chart(db_session, user_id, start_date, end_date, scope)
    promotion_dynamics = await _get_promotion_dynamics(db_session, user_id, start_date, end_date, scope)
    articles_table = await _get_articles_table(db_session, user_id, start_date, end_date, orders_by_nm, scope)

    return response_success(data={
        "funnel": _get_funnel_data(advertising, orders),
        "conversions": _get_conversion_data(advertising),
        "acquisition_cost": _get_acquisition_cost_data(advertising, orders),
        "dynamics_chart": dynamics_chart,
        "promotion_dynamics": promotion_dynamics,
        "articles_table": articles_table,
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "selected_token_id": str(scope.selected_token_id) if scope.selected_token_id else None,
    })
