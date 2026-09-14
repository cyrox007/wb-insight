from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.logger import setup_logger
from core.middleware import auth_middle
from models.tokens_model import Marketplace
from models.wb_advertising_stats import WbAdvertisingStats
from services.dashboard.semantic_metrics import (
    AdvertisingTotals,
    OrderTotals,
    get_advertising_totals,
    get_order_totals,
    get_order_totals_by_nm,
    is_auth_sync_error,
)
from services.token_services import get_tokens_by_user_id
from services.user_sync_state_service import get_user_sync_states
from services.wb_advertising_service import get_advertising_stats_by_day
from utils.responce_helps import response_error, response_success


logger = setup_logger(__name__)
router = APIRouter(prefix="/dashboard/ads", tags=["Advertising"])


def _get_funnel_data(
    advertising: AdvertisingTotals,
    orders: OrderTotals,
) -> Dict[str, Any]:
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
    ctr = (
        advertising.clicks / advertising.views * 100 if advertising.views else 0.0
    )
    cr_to_cart = (
        advertising.added_to_cart / advertising.clicks * 100
        if advertising.clicks
        else 0.0
    )
    conversion_click_to_order = (
        advertising.orders / advertising.clicks * 100
        if advertising.clicks
        else 0.0
    )
    cpc = advertising.spend / advertising.clicks if advertising.clicks else 0.0
    cpm = advertising.spend / advertising.views * 1000 if advertising.views else 0.0
    drr = (
        advertising.spend / advertising.orders_amount * 100
        if advertising.orders_amount
        else 0.0
    )
    return {
        "expenses": round(advertising.spend, 2),
        "ctr": round(ctr, 2),
        "cr_to_cart": round(cr_to_cart, 2),
        "conversion_click_to_order": round(conversion_click_to_order, 2),
        "cpc": round(cpc, 2),
        "cpm": round(cpm, 2),
        "drr": round(drr, 2),
    }


def _get_acquisition_cost_data(
    advertising: AdvertisingTotals,
    orders: OrderTotals,
) -> Dict[str, Any]:
    avg_order_value = orders.amount / orders.count if orders.count else 0.0
    cost_per_view = advertising.spend / advertising.views if advertising.views else 0.0
    cost_per_click = (
        advertising.spend / advertising.clicks if advertising.clicks else 0.0
    )
    cost_per_cart = (
        advertising.spend / advertising.added_to_cart
        if advertising.added_to_cart
        else 0.0
    )
    cpo = advertising.spend / advertising.orders if advertising.orders else 0.0

    # Business target remains configurable in a later planning package.
    norm_drr = 10.0
    max_cpm = avg_order_value * norm_drr / 100 if avg_order_value > 0 else 0.0
    return {
        "avg_order_value": round(avg_order_value, 2),
        "cost_per_view": round(cost_per_view, 2),
        "cost_per_click": round(cost_per_click, 2),
        "cost_per_cart": round(cost_per_cart, 2),
        "cpo": round(cpo, 2),
        "norm_drr": norm_drr,
        "max_cpm": round(max_cpm, 2),
    }


async def _get_promotion_dynamics(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
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
    rows = (await session.execute(query)).fetchall()
    data = []
    for row in rows:
        views = int(row.views or 0)
        clicks = int(row.clicks or 0)
        amount = float(row.amount or 0)
        data.append(
            {
                "date": row.date.isoformat(),
                "ctr": round(clicks / views * 100, 2) if views else 0.0,
                "cpm": round(amount / views * 1000, 2) if views else 0.0,
                "amount": round(amount, 2),
            }
        )
    return data


async def _get_articles_table(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    orders_by_nm: dict[int, OrderTotals],
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
    rows = (await session.execute(query)).fetchall()

    data: list[dict[str, Any]] = []
    for row in rows:
        nm_id = int(row.nm_id)
        total_orders = orders_by_nm.get(nm_id, OrderTotals())
        views = int(row.total_views or 0)
        clicks = int(row.total_clicks or 0)
        atc = int(row.total_atc or 0)
        ad_orders = int(row.ad_orders or 0)
        spend = float(row.total_amount or 0)
        ad_orders_amount = float(row.ad_orders_amount or 0)
        ctr = float(row.avg_ctr or 0)
        cr = float(row.avg_cr or 0)
        cpc = float(row.avg_cpc or 0)

        cart_to_order = ad_orders / atc * 100 if atc else 0.0
        click_to_order = ad_orders / clicks * 100 if clicks else 0.0
        order_cost_in_ads = spend / ad_orders if ad_orders else 0.0
        drr_from_orders = spend / total_orders.amount * 100 if total_orders.amount else 0.0
        cpm = spend / views * 1000 if views else 0.0

        data.append(
            {
                "nm_id": nm_id,
                "product_name": row.product_name or "",
                "views": views,
                "clicks": clicks,
                "added_to_cart": atc,
                "ad_orders": ad_orders,
                "ad_orders_amount": round(ad_orders_amount, 2),
                "total_orders": total_orders.count,
                "total_orders_amount": round(total_orders.amount, 2),
                "expenses": round(spend, 2),
                "ctr": round(ctr, 2),
                "cr": round(cr, 2),
                "cart_to_order": round(cart_to_order, 2),
                "click_to_order": round(click_to_order, 2),
                "cpc": round(cpc, 2),
                "order_cost_in_ads": round(order_cost_in_ads, 2),
                "drr_from_orders": round(drr_from_orders, 2),
                "cpm": round(cpm, 2),
            }
        )
    return data


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_advertising_stats(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = request.state.user["sub"]
    states = await get_user_sync_states(session=db_session, user_id=user_id)
    sync_errors = [state.last_error for state in states if state.last_error]

    user_tokens = await get_tokens_by_user_id(db_session, user_id)
    valid_wb_tokens = [
        token
        for token in user_tokens
        if token.marketplace == Marketplace.WILDBERRIES and token.is_valid
    ]
    if not valid_wb_tokens:
        auth_errors = [error for error in sync_errors if is_auth_sync_error(error)]
        if auth_errors:
            return response_error(
                message=(
                    "Ошибка авторизации: подключение недействительно или истекло. "
                    "Пожалуйста, обновите кабинет Wildberries в настройках."
                ),
                code="TOKEN_INVALID",
            )
        return response_error(
            message=(
                "Нет действительных токенов для синхронизации. "
                "Пожалуйста, добавьте актуальный токен Wildberries."
            ),
            code="NO_VALID_TOKENS",
        )

    # Keep one AsyncSession serialized; each query is executed one at a time.
    advertising = await get_advertising_totals(
        db_session, user_id, start_date, end_date
    )
    orders = await get_order_totals(db_session, user_id, start_date, end_date)
    orders_by_nm = await get_order_totals_by_nm(
        db_session, user_id, start_date, end_date
    )
    dynamics_chart = await get_advertising_stats_by_day(
        db_session, user_id, start_date, end_date
    )
    promotion_dynamics = await _get_promotion_dynamics(
        db_session, user_id, start_date, end_date
    )
    articles_table = await _get_articles_table(
        db_session, user_id, start_date, end_date, orders_by_nm
    )

    return response_success(
        data={
            "funnel": _get_funnel_data(advertising, orders),
            "conversions": _get_conversion_data(advertising),
            "acquisition_cost": _get_acquisition_cost_data(advertising, orders),
            "dynamics_chart": dynamics_chart,
            "promotion_dynamics": promotion_dynamics,
            "articles_table": articles_table,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        }
    )
