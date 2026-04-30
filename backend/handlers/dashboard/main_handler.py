import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from core.dependencies import get_db_session
from core.logger import setup_logger
from core.middleware import auth_middle
from utils.responce_helps import response_error, response_success
from services.wb_report_service import (
    check_wb_report_stats, 
    get_base_wb_report_stats, 
    get_returns_wb_report_stats, 
    get_sales_wb_report_stats, 
    get_chart_data, 
    get_warehouse_data, 
    get_category_data, 
    get_abc_analysis, 
    get_size_chart
)
from services.cost_price_service import get_dashboard_unit_economy

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = setup_logger(__name__)

def _calc_change(current: float, previous: float) -> tuple[float, float]:
    """Расчёт абсолютного и процентного изменения"""
    change_abs = current - previous
    change_percent = (change_abs / previous * 100) if previous != 0 else (100.0 if current > 0 else 0.0)
    return round(change_abs, 2), round(change_percent, 1)

async def _calculate_stats(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> dict:
    """Вычисляет основную статистику дашборда"""
    days_in_period = (end_date - start_date).days if end_date and start_date else 30
    days_in_month = 30

    # Параллельно выполняем запросы для текущего периода
    base_result, sales_result, returns_result, unit_economy = await asyncio.gather(
        get_base_wb_report_stats(session=session, user_id=user_id, start_date=start_date, end_date=end_date),
        get_sales_wb_report_stats(session=session, user_id=user_id, start_date=start_date, end_date=end_date),
        get_returns_wb_report_stats(session=session, user_id=user_id, start_date=start_date, end_date=end_date),
        get_dashboard_unit_economy(session=session, user_id=user_id, start_date=start_date, end_date=end_date),
    )

    # Расчёт метрик текущего периода
    ordered_amount = float(getattr(base_result, 'ordered_amount', 0) or 0)
    ordered_units = int(getattr(base_result, 'ordered_units', 0) or 0)
    sales_amount = float(getattr(sales_result, 'sales_amount', 0) or 0)
    sales_units = int(getattr(sales_result, 'sales_units', 0) or 0)
    returns_amount = float(getattr(returns_result, 'returns_amount', 0) or 0)
    to_pay = float(getattr(base_result, 'to_pay', 0) or 0)

    revenue = sales_amount - returns_amount
    profit = unit_economy['total_profit']
    marginality = unit_economy['avg_margin_percent']
    profitability = (profit / to_pay * 100) if to_pay > 0 else 0.0
    ddr = unit_economy['avg_drr_percent']
    buyout_rate = (sales_units / ordered_units * 100) if ordered_units else 0.0
    avg_price = (ordered_amount / ordered_units) if ordered_units else 0.0

    # План и прогноз
    fact_current_month = revenue
    plan_current_month = revenue * 1.2 if revenue > 0 else 50000000
    done = (fact_current_month / plan_current_month * 100) if plan_current_month > 0 else 0.0
    forecast = (fact_current_month / days_in_period * days_in_month) if days_in_period > 0 else fact_current_month
    recommended_orders_per_day = (plan_current_month - fact_current_month) / max(1, (days_in_month - days_in_period)) if days_in_month > days_in_period else 0.0

    # Данные за предыдущий период
    prev_start_date = start_date - timedelta(days=days_in_period)
    prev_end_date = start_date

    prev_base_result, prev_sales_result, prev_returns_result, prev_unit_economy = await asyncio.gather(
        get_base_wb_report_stats(session=session, user_id=user_id, start_date=prev_start_date, end_date=prev_end_date),
        get_sales_wb_report_stats(session=session, user_id=user_id, start_date=prev_start_date, end_date=prev_end_date),
        get_returns_wb_report_stats(session=session, user_id=user_id, start_date=prev_start_date, end_date=prev_end_date),
        get_dashboard_unit_economy(session=session, user_id=user_id, start_date=prev_start_date, end_date=prev_end_date),
    )

    prev_ordered_amount = float(getattr(prev_base_result, 'ordered_amount', 0) or 0)
    prev_ordered_units = int(getattr(prev_base_result, 'ordered_units', 0) or 0)
    prev_sales_units = int(getattr(prev_sales_result, 'sales_units', 0) or 0)
    prev_revenue = float(getattr(prev_sales_result, 'sales_amount', 0) or 0) - float(getattr(prev_returns_result, 'returns_amount', 0) or 0)
    prev_to_pay = float(getattr(prev_base_result, 'to_pay', 0) or 0)
    prev_profit = prev_unit_economy['total_profit']
    prev_buyout_rate = (prev_sales_units / prev_ordered_units * 100) if prev_ordered_units else 0.0
    prev_avg_price = (prev_ordered_amount / prev_ordered_units) if prev_ordered_units else 0.0

    # Расчёт изменений
    ordered_amount_change_abs, ordered_amount_change_percent = _calc_change(ordered_amount, prev_ordered_amount)
    ordered_units_change_abs, ordered_units_change_percent = _calc_change(ordered_units, prev_ordered_units)
    revenue_change_abs, revenue_change_percent = _calc_change(revenue, prev_revenue)
    sales_units_change_abs, sales_units_change_percent = _calc_change(sales_units, prev_sales_units)
    to_pay_change_abs, to_pay_change_percent = _calc_change(to_pay, prev_to_pay)
    profit_change_abs, profit_change_percent = _calc_change(profit, prev_profit)
    buyout_rate_change_abs, buyout_rate_change_percent = _calc_change(buyout_rate, prev_buyout_rate)
    avg_price_change_abs, avg_price_change_percent = _calc_change(avg_price, prev_avg_price)

    return {
        "stats": {
            "ordered_amount": {"value": round(ordered_amount, 2), "change_percent": ordered_amount_change_percent, "change_abs": ordered_amount_change_abs},
            "ordered_units": {"value": ordered_units, "change_percent": ordered_units_change_percent, "change_abs": ordered_units_change_abs},
            "revenue": {"value": round(revenue, 2), "change_percent": revenue_change_percent, "change_abs": revenue_change_abs},
            "sold_units": {"value": sales_units, "change_percent": sales_units_change_percent, "change_abs": sales_units_change_abs},
            "to_pay": {"value": round(to_pay, 2), "change_percent": to_pay_change_percent, "change_abs": to_pay_change_abs},
            "profit": {"value": round(profit, 2), "change_percent": profit_change_percent, "change_abs": profit_change_abs},
            "buyout_rate": {"value": round(buyout_rate, 1), "change_percent": buyout_rate_change_percent, "change_abs": round(buyout_rate_change_abs, 1)},
            "avg_price": {"value": round(avg_price, 2), "change_percent": avg_price_change_percent, "change_abs": round(avg_price_change_abs, 2)},
            "marginality": {"value": round(marginality, 1) if marginality else 0.0},
            "profitability": {"value": round(profitability, 1) if profitability else 0.0},
            "ddr": {"value": round(ddr, 2) if ddr else 0.0},
            "fact_current_month": {"value": round(fact_current_month, 2)},
            "plan_current_month": {"value": round(plan_current_month, 2)},
            "done": {"value": round(done, 2)},
            "forecast": {"value": round(forecast, 0)},
            "recommended_orders_per_day": {"value": round(recommended_orders_per_day, 2)}
        },
        "base_stats": {
            # Первая группа - пока без данных (нужен отдельный сервис для рекламы)
            'adViews': 0,                   # Просмотры Рекламы
            'clicks': 0,                    # Клики
            'clicksPercentage': 0.0,        # % кликов от просмотров
            'addToCart': 0,                 # Добавлено в корзину
            'addToCartPercentage': 0.0,     # % добавлений от кликов

            # Вторая группа
            'orderedTotalCount': ordered_units,     # Заказано всего (количество)
            'orderedTotalAmount': ordered_amount,   # Заказано всего (сумма)
            'boughtTotalCount': sales_units,        # Выкуплено всего (количество)
            'boughtTotalAmount': sales_amount,      # Выкуплено всего (сумма)
            'buyoutPercent': round(buyout_rate, 2), # Процент выкупа

            # Третья группа
            'avgOrderValue': round(avg_price, 2),                                       # Средняя стоимость заказа
            'marginality': round(marginality, 1) if marginality else 0.0,               # Маржинальность (%)
            'expenseRatio': round(ddr, 1) if ddr else 0.0,                              # Доля расходов от продаж (%)
            'profit': round(profit, 2),                                                 # Прибыль
            'revenue': round(revenue, 2),                                               # Выручка
            'logistics': round(float(getattr(base_result, 'logistics', 0) or 0), 2),    # Логистика
            'storage': round(float(getattr(base_result, 'storage_fee', 0) or 0), 2)     # Хранение
        }
    }

@router.get("/", dependencies=[Depends(auth_middle)])
async def dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """Основной эндпоинт дашборда - возвращает только быстрые данные"""
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)

    current_user = request.state.user

    # Быстрая проверка наличия данных
    report_count = await check_wb_report_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )

    if report_count == 0:
        return response_error(
            message="Данные отсутствуют → не синхронизировано",
            code="NOT_DATA"
        )

    # Получаем только основную статистику (быстро)
    stats_data = await _calculate_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )

    # Возвращаем базовые данные сразу, остальное можно дозагрузить отдельно
    return response_success(
        is_synced=True,
        stats=stats_data["stats"],
        chartData=[],  # Пустой массив - фронт покажет заглушку
        baseStats=stats_data["base_stats"],
        abcAnalysis=[],
        warehouseData=[],
        sizeChart=[],
        categoryData=[],
        partial=True  # Флаг что данные частичные
    )

@router.get("/charts", dependencies=[Depends(auth_middle)])
async def dashboard_charts(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """Эндпоинт для загрузки данных графиков (тяжёлые данные)"""
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)
    current_user = request.state.user

    # Параллельно загружаем все тяжёлые данные
    chartData, warehouseData, abcAnalysis, categoryData, sizeChart = await asyncio.gather(
        get_chart_data(session=db_session, user_id=current_user['sub'], start_date=start_date, end_date=end_date),
        get_warehouse_data(session=db_session, user_id=current_user['sub']),
        get_abc_analysis(session=db_session, user_id=current_user['sub'], start_date=start_date, end_date=end_date),
        get_category_data(session=db_session, user_id=current_user['sub'], start_date=start_date, end_date=end_date),
        get_size_chart(session=db_session, user_id=current_user['sub'], start_date=start_date, end_date=end_date),
    )

    return response_success(
        chartData=chartData,
        warehouseData=warehouseData,
        abcAnalysis=abcAnalysis,
        categoryData=categoryData,
        sizeChart=sizeChart
    )