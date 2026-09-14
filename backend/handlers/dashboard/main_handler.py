from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.logger import setup_logger
from core.middleware import auth_middle
from services.dashboard.account_scope import (
    DashboardAccountUnavailableError,
    resolve_dashboard_token_id,
)
from services.dashboard.finance_metrics import (
    get_abc_analysis,
    get_base_report_stats,
    get_category_data,
    get_chart_data,
    get_returns_report_stats,
    get_sales_report_stats,
    get_size_chart,
    get_warehouse_data,
)
from services.dashboard.semantic_metrics import (
    get_advertising_totals,
    get_order_totals,
    has_active_sync_jobs,
    inclusive_days,
    is_auth_sync_error,
    previous_period,
)
from services.dashboard.unit_economy_scope import get_dashboard_unit_economy_scoped
from services.marketplace_access_service import get_allowed_wb_tokens
from services.user_sync_state_service import get_user_sync_states
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
    token_id: UUID | None = None,
) -> dict:
    days_in_period = inclusive_days(start_date, end_date)
    days_in_month = 30

    base_result = await get_base_report_stats(
        session, user_id, start_date, end_date, token_id
    )
    sales_result = await get_sales_report_stats(
        session, user_id, start_date, end_date, token_id
    )
    returns_result = await get_returns_report_stats(
        session, user_id, start_date, end_date, token_id
    )
    unit_economy = await get_dashboard_unit_economy_scoped(
        session, user_id, start_date, end_date, token_id
    )
    orders = await get_order_totals(
        session, user_id, start_date, end_date, token_id
    )
    advertising = await get_advertising_totals(
        session, user_id, start_date, end_date, token_id
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
    profitability = profit / to_pay * 100 if to_pay > 0 else 0.0
    ddr = float(unit_economy["avg_drr_percent"] or 0)
    buyout_rate = sales_units / ordered_units * 100 if ordered_units else 0.0
    avg_price = ordered_amount / ordered_units if ordered_units else 0.0

    fact_current_month = revenue
    plan_current_month = revenue * 1.2 if revenue > 0 else 50000000
    done = fact_current_month / plan_current_month * 100 if plan_current_month > 0 else 0.0
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
    prev_base_result = await get_base_report_stats(
        session, user_id, prev_start_date, prev_end_date, token_id
    )
    prev_sales_result = await get_sales_report_stats(
        session, user_id, prev_start_date, prev_end_date, token_id
    )
    prev_returns_result = await get_returns_report_stats(
        session, user_id, prev_start_date, prev_end_date, token_id
    )
    prev_unit_economy = await get_dashboard_unit_economy_scoped(
        session, user_id, prev_start_date, prev_end_date, token_id
    )
    prev_orders = await get_order_totals(
        session, user_id, prev_start_date, prev_end_date, token_id
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

    click_rate = advertising.clicks / advertising.views * 100 if advertising.views else 0.0
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


async def _resolve_scope_or_error(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID | None,
):
    try:
        return await resolve_dashboard_token_id(session, user_id, token_id), None
    except DashboardAccountUnavailableError as exc:
        return None, response_error(
            code="ACCOUNT_NOT_AVAILABLE",
            message=str(exc),
        )


@router.get("/", dependencies=[Depends(auth_middle)])
async def dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    token_id: Optional[UUID] = None,
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    token_id, scope_error = await _resolve_scope_or_error(db_session, user_id, token_id)
    if scope_error is not None:
        return scope_error

    states = await get_user_sync_states(session=db_session, user_id=user_id)
    scoped_states = [
        state for state in states if token_id is None or state.token_id == token_id
    ]
    has_any_success = any(state.last_success_at is not None for state in scoped_states)
    sync_errors = [state.last_error for state in scoped_states if state.last_error]

    allowed_tokens = await get_allowed_wb_tokens(db_session, user_id)
    has_valid_tokens = bool(allowed_tokens) if token_id is None else True
    auth_errors = [error for error in sync_errors if is_auth_sync_error(error)]

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

    is_sync_running = await has_active_sync_jobs(db_session, user_id, token_id)

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
        db_session, user_id, start_date, end_date, token_id
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
        selected_token_id=str(token_id) if token_id else None,
    )


@router.get("/charts", dependencies=[Depends(auth_middle)])
async def dashboard_charts(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    token_id: Optional[UUID] = None,
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    token_id, scope_error = await _resolve_scope_or_error(db_session, user_id, token_id)
    if scope_error is not None:
        return scope_error

    chart_data = await get_chart_data(
        db_session, user_id, start_date, end_date, token_id
    )
    warehouse_data = await get_warehouse_data(db_session, user_id, token_id)
    abc_analysis = await get_abc_analysis(
        db_session, user_id, start_date, end_date, token_id
    )
    category_data = await get_category_data(
        db_session, user_id, start_date, end_date, token_id
    )
    size_chart = await get_size_chart(
        db_session, user_id, start_date, end_date, token_id
    )

    return response_success(
        chartData=chart_data,
        warehouseData=warehouse_data,
        abcAnalysis=abc_analysis,
        categoryData=category_data,
        sizeChart=size_chart,
        selected_token_id=str(token_id) if token_id else None,
    )
