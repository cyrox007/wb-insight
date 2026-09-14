from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.logger import setup_logger
from core.middleware import auth_middle
from models.tokens_model import Marketplace
from services.cost_price_service import get_dashboard_unit_economy
from services.dashboard.semantic_metrics import (
    get_advertising_totals,
    get_order_totals,
    has_active_sync_jobs,
    inclusive_days,
    is_auth_sync_error,
    previous_period,
)
from services.token_services import get_tokens_by_user_id
from services.user_sync_state_service import get_user_sync_states
from services.wb_report_service import (
    get_abc_analysis,
    get_base_wb_report_stats,
    get_category_data,
    get_chart_data,
    get_returns_wb_report_stats,
    get_sales_wb_report_stats,
    get_size_chart,
    get_warehouse_data,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = setup_logger(__name__)


def _calc_change(current: float, previous: float) -> tuple[float, float]:
    change_abs = current - previous
    change_percent = (
        change_abs / previous * 100
        if previous != 0
        else (100.0 if current > 0 else 0.0)
    )
    return round(change_abs, 2), round(change_percent, 1)


async def _calculate_stats(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> dict:
    days_in_period = inclusive_days(start_date, end_date)
    days_in_month = 30

    # AsyncSession must not execute multiple statements concurrently.
    base_result = await get_base_wb_report_stats(
        session=session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    sales_result = await get_sales_wb_report_stats(
        session=session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    returns_result = await get_returns_wb_report_stats(
        session=session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    unit_economy = await get_dashboard_unit_economy(
        session=session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    orders = await get_order_totals(session, user_id, start_date, end_date)
    advertising = await get_advertising_totals(
        session, user_id, start_date, end_date
    )

    ordered_amount = orders.amount
    ordered_units = orders.count
    sales_amount = float(getattr(sales_result, "sales_amount", 0) or 0)
    sales_units = int(getattr(sales_result, "sales_units", 0) or 0)
    returns_amount = float(getattr(returns_result, "returns_amount", 0) or 0)
    to_pay = float(getattr(base_result, "to_pay", 0) or 0)

    revenue = sales_amount - returns_amount
    profit = float(unit_economy["total_profit"] or 0)
    marginality = float(unit_economy["avg_margin_percent"] or 0)
    profitability = (profit / to_pay * 100) if to_pay > 0 else 0.0
    ddr = float(unit_economy["avg_drr_percent"] or 0)
    buyout_rate = (sales_units / ordered_units * 100) if ordered_units else 0.0
    avg_price = (ordered_amount / ordered_units) if ordered_units else 0.0

    fact_current_month = revenue
    plan_current_month = revenue * 1.2 if revenue > 0 else 50000000
    done = (
        fact_current_month / plan_current_month * 100
        if plan_current_month > 0
        else 0.0
    )
    forecast = (
        fact_current_month / days_in_period * days_in_month
        if days_in_period > 0
        else fact_current_month
    )
    recommended_orders_per_day = (
        (plan_current_month - fact_current_month)
        / max(1, days_in_month - days_in_period)
        if days_in_month > days_in_period
        else 0.0
    )

    prev_start_date, prev_end_date = previous_period(start_date, end_date)
    prev_base_result = await get_base_wb_report_stats(
        session=session,
        user_id=user_id,
        start_date=prev_start_date,
        end_date=prev_end_date,
    )
    prev_sales_result = await get_sales_wb_report_stats(
        session=session,
        user_id=user_id,
        start_date=prev_start_date,
        end_date=prev_end_date,
    )
    prev_returns_result = await get_returns_wb_report_stats(
        session=session,
        user_id=user_id,
        start_date=prev_start_date,
        end_date=prev_end_date,
    )
    prev_unit_economy = await get_dashboard_unit_economy(
        session=session,
        user_id=user_id,
        start_date=prev_start_date,
        end_date=prev_end_date,
    )
    prev_orders = await get_order_totals(
        session, user_id, prev_start_date, prev_end_date
    )

    prev_ordered_amount = prev_orders.amount
    prev_ordered_units = prev_orders.count
    prev_sales_units = int(getattr(prev_sales_result, "sales_units", 0) or 0)
    prev_revenue = float(getattr(prev_sales_result, "sales_amount", 0) or 0) - float(
        getattr(prev_returns_result, "returns_amount", 0) or 0
    )
    prev_to_pay = float(getattr(prev_base_result, "to_pay", 0) or 0)
    prev_profit = float(prev_unit_economy["total_profit"] or 0)
    prev_buyout_rate = (
        prev_sales_units / prev_ordered_units * 100 if prev_ordered_units else 0.0
    )
    prev_avg_price = (
        prev_ordered_amount / prev_ordered_units if prev_ordered_units else 0.0
    )

    ordered_amount_change_abs, ordered_amount_change_percent = _calc_change(
        ordered_amount, prev_ordered_amount
    )
    ordered_units_change_abs, ordered_units_change_percent = _calc_change(
        ordered_units, prev_ordered_units
    )
    revenue_change_abs, revenue_change_percent = _calc_change(revenue, prev_revenue)
    sales_units_change_abs, sales_units_change_percent = _calc_change(
        sales_units, prev_sales_units
    )
    to_pay_change_abs, to_pay_change_percent = _calc_change(to_pay, prev_to_pay)
    profit_change_abs, profit_change_percent = _calc_change(profit, prev_profit)
    buyout_rate_change_abs, buyout_rate_change_percent = _calc_change(
        buyout_rate, prev_buyout_rate
    )
    avg_price_change_abs, avg_price_change_percent = _calc_change(
        avg_price, prev_avg_price
    )

    click_rate = (
        advertising.clicks / advertising.views * 100 if advertising.views else 0.0
    )
    cart_rate = (
        advertising.added_to_cart / advertising.clicks * 100
        if advertising.clicks
        else 0.0
    )

    return {
        "stats": {
            "ordered_amount": {
                "value": round(ordered_amount, 2),
                "change_percent": ordered_amount_change_percent,
                "change_abs": ordered_amount_change_abs,
            },
            "ordered_units": {
                "value": ordered_units,
                "change_percent": ordered_units_change_percent,
                "change_abs": ordered_units_change_abs,
            },
            "revenue": {
                "value": round(revenue, 2),
                "change_percent": revenue_change_percent,
                "change_abs": revenue_change_abs,
            },
            "sold_units": {
                "value": sales_units,
                "change_percent": sales_units_change_percent,
                "change_abs": sales_units_change_abs,
            },
            "to_pay": {
                "value": round(to_pay, 2),
                "change_percent": to_pay_change_percent,
                "change_abs": to_pay_change_abs,
            },
            "profit": {
                "value": round(profit, 2),
                "change_percent": profit_change_percent,
                "change_abs": profit_change_abs,
            },
            "buyout_rate": {
                "value": round(buyout_rate, 1),
                "change_percent": buyout_rate_change_percent,
                "change_abs": round(buyout_rate_change_abs, 1),
            },
            "avg_price": {
                "value": round(avg_price, 2),
                "change_percent": avg_price_change_percent,
                "change_abs": round(avg_price_change_abs, 2),
            },
            "marginality": {"value": round(marginality, 1)},
            "profitability": {"value": round(profitability, 1)},
            "ddr": {"value": round(ddr, 2)},
            "fact_current_month": {"value": round(fact_current_month, 2)},
            "plan_current_month": {"value": round(plan_current_month, 2)},
            "done": {"value": round(done, 2)},
            "forecast": {"value": round(forecast, 0)},
            "recommended_orders_per_day": {
                "value": round(recommended_orders_per_day, 2)
            },
        },
        "base_stats": {
            "adViews": advertising.views,
            "clicks": advertising.clicks,
            "clicksPercentage": round(click_rate, 2),
            "addToCart": advertising.added_to_cart,
            "addToCartPercentage": round(cart_rate, 2),
            "orderedTotalCount": ordered_units,
            "orderedTotalAmount": round(ordered_amount, 2),
            "boughtTotalCount": sales_units,
            "boughtTotalAmount": round(sales_amount, 2),
            "buyoutPercent": round(buyout_rate, 2),
            "avgOrderValue": round(avg_price, 2),
            "marginality": round(marginality, 1),
            "expenseRatio": round(ddr, 1),
            "profit": round(profit, 2),
            "revenue": round(revenue, 2),
            "logistics": round(float(getattr(base_result, "logistics", 0) or 0), 2),
            "storage": round(float(getattr(base_result, "storage_fee", 0) or 0), 2),
        },
    }


@router.get("/", dependencies=[Depends(auth_middle)])
async def dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    current_user = request.state.user
    user_id = current_user["sub"]
    states = await get_user_sync_states(session=db_session, user_id=user_id)
    has_any_success = any(state.last_success_at is not None for state in states)
    sync_errors = [state.last_error for state in states if state.last_error]

    user_tokens = await get_tokens_by_user_id(db_session, user_id)
    valid_wb_tokens = [
        token
        for token in user_tokens
        if token.marketplace == Marketplace.WILDBERRIES and token.is_valid
    ]
    has_valid_tokens = bool(valid_wb_tokens)
    auth_errors = [error for error in sync_errors if is_auth_sync_error(error)]

    # One expired account must not block other valid seller accounts.
    if not has_valid_tokens:
        if auth_errors:
            return response_error(
                message=(
                    "Ошибка авторизации: подключение недействительно или истекло. "
                    "Обновите кабинет Wildberries в настройках."
                ),
                code="TOKEN_INVALID",
            )
        if not has_any_success:
            return response_error(
                message=(
                    "Нет действительных токенов для синхронизации. "
                    "Пожалуйста, добавьте актуальный токен Wildberries."
                ),
                code="NO_VALID_TOKENS",
            )

    is_sync_running = await has_active_sync_jobs(db_session, user_id)

    if not has_any_success and sync_errors:
        return response_error(
            message=f"Ошибка синхронизации: {sync_errors[0]}",
            code="SYNC_ERROR",
        )

    if not has_any_success:
        return response_error(
            message="Данные отсутствуют → синхронизация не запускалась",
            code="NOT_SYNCED",
        )

    if is_sync_running:
        return response_success(
            is_synced=False,
            is_syncing=True,
            message="Идёт синхронизация данных",
            stats={},
            partial=True,
        )

    stats_data = await _calculate_stats(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return response_success(
        is_synced=True,
        stats=stats_data["stats"],
        chartData=[],
        baseStats=stats_data["base_stats"],
        abcAnalysis=[],
        warehouseData=[],
        sizeChart=[],
        categoryData=[],
        partial=True,
    )


@router.get("/charts", dependencies=[Depends(auth_middle)])
async def dashboard_charts(
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

    # Keep one AsyncSession serialized; do not run concurrent execute calls on it.
    chart_data = await get_chart_data(
        session=db_session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    warehouse_data = await get_warehouse_data(session=db_session, user_id=user_id)
    abc_analysis = await get_abc_analysis(
        session=db_session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    category_data = await get_category_data(
        session=db_session, user_id=user_id, start_date=start_date, end_date=end_date
    )
    size_chart = await get_size_chart(
        session=db_session, user_id=user_id, start_date=start_date, end_date=end_date
    )

    return response_success(
        chartData=chart_data,
        warehouseData=warehouse_data,
        abcAnalysis=abc_analysis,
        categoryData=category_data,
        sizeChart=size_chart,
    )
