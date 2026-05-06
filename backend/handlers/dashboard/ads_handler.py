"""
Хендлер для страницы рекламной статистики

Предоставляет данные для страницы "Внутренняя реклама":
- Динамика просмотров (график по дням)
- Рекламная воронка
- Конверсии по воронке
- Расчет стоимости привлечения
- Динамика продвижения (CTR, CPM, сумма)
- Таблица по артикулам
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.dependencies import get_db_session
from core.logger import setup_logger
from core.middleware import auth_middle
from models.wb_advertising_stats import WbAdvertisingStats
from services.wb_advertising_service import (
    get_aggregated_advertising_stats,
    get_advertising_stats_by_day,
    get_total_advertising_cost_for_user,
)
from services.user_sync_state_service import get_user_sync_states
from services.token_services import get_tokens_by_user_id
from models.tokens_model import Marketplace
from utils.responce_helps import response_error, response_success


logger = setup_logger(__name__)

router = APIRouter(prefix='/dashboard/ads', tags=['Advertising'])


def _calc_change(current: float, previous: float) -> tuple[float, float]:
    """Расчёт абсолютного и процентного изменения"""
    change_abs = current - previous
    change_percent = (change_abs / previous * 100) if previous != 0 else (100.0 if current > 0 else 0.0)
    return round(change_abs, 2), round(change_percent, 1)


async def _get_funnel_data(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Получить данные для рекламной воронки
    
    Returns:
        Dict с данными воронки:
        - views: Просмотры
        - clicks: Переходы
        - added_to_cart: Добавлений в корзину
        - ad_orders: Заказов с помощью рекламы
        - ad_orders_amount: На сумму (рекламные заказы)
        - total_orders: Общих заказов
        - total_orders_amount: На сумму (общие заказы)
    """
    # Агрегируем данные из таблицы рекламы
    query = select(
        func.sum(WbAdvertisingStats.views).label("total_views"),
        func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
        func.sum(WbAdvertisingStats.added_to_cart).label("total_atc"),
        func.sum(WbAdvertisingStats.orders).label("total_orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("total_orders_amount"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    # Для общих заказов пока используем данные из рекламы
    # В будущем можно объединить с данными из отчетов
    return {
        "views": int(row.total_views or 0),
        "clicks": int(row.total_clicks or 0),
        "added_to_cart": int(row.total_atc or 0),
        "ad_orders": int(row.total_orders or 0),
        "ad_orders_amount": float(row.total_orders_amount or 0),
        "total_orders": int(row.total_orders or 0),  # Пока одинаково
        "total_orders_amount": float(row.total_orders_amount or 0),
    }


async def _get_conversion_data(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Получить данные для блока конверсий
    
    Returns:
        Dict с метриками:
        - expenses: Расходы на рекламу
        - ctr: CTR
        - cr_to_cart: CR в корзину
        - conversion_click_to_order: Конверсия из перехода в заказ
        - cpc: CPC
        - cpm: CPM
        - drr: ДРР
    """
    query = select(
        func.sum(WbAdvertisingStats.views).label("total_views"),
        func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
        func.sum(WbAdvertisingStats.amount).label("total_amount"),
        func.sum(WbAdvertisingStats.added_to_cart).label("total_atc"),
        func.sum(WbAdvertisingStats.orders).label("total_orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("total_orders_amount"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    total_views = int(row.total_views or 0)
    total_clicks = int(row.total_clicks or 0)
    total_amount = float(row.total_amount or 0)
    total_atc = int(row.total_atc or 0)
    total_orders = int(row.total_orders or 0)
    total_orders_amount = float(row.total_orders_amount or 0)
    
    # Рассчитываем метрики
    ctr = (total_clicks / total_views * 100) if total_views > 0 else 0
    cr_to_cart = (total_atc / total_clicks * 100) if total_clicks > 0 else 0
    conversion_click_to_order = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    cpc = (total_amount / total_clicks) if total_clicks > 0 else 0
    cpm = (total_amount / total_views * 1000) if total_views > 0 else 0
    drr = (total_amount / total_orders_amount * 100) if total_orders_amount > 0 else 0
    
    return {
        "expenses": round(total_amount, 2),
        "ctr": round(ctr, 2),
        "cr_to_cart": round(cr_to_cart, 2),
        "conversion_click_to_order": round(conversion_click_to_order, 2),
        "cpc": round(cpc, 2),
        "cpm": round(cpm, 2),
        "drr": round(drr, 2),
    }


async def _get_acquisition_cost_data(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Получить данные для блока расчета стоимости привлечения
    
    Returns:
        Dict с метриками:
        - avg_order_value: Средняя стоимость заказа
        - cost_per_view: Стоимость просмотра
        - cost_per_click: Стоимость перехода
        - cost_per_cart: Стоимость добавления в корзину
        - cpo: CPO (стоимость одного заказа)
        - norm_drr: Норма ДРР (заглушка 10%)
        - max_cpm: max Допустимый CPM
    """
    query = select(
        func.sum(WbAdvertisingStats.views).label("total_views"),
        func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
        func.sum(WbAdvertisingStats.amount).label("total_amount"),
        func.sum(WbAdvertisingStats.added_to_cart).label("total_atc"),
        func.sum(WbAdvertisingStats.orders).label("total_orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("total_orders_amount"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    total_views = int(row.total_views or 0)
    total_clicks = int(row.total_clicks or 0)
    total_amount = float(row.total_amount or 0)
    total_atc = int(row.total_atc or 0)
    total_orders = int(row.total_orders or 0)
    total_orders_amount = float(row.total_orders_amount or 0)
    
    # Рассчитываем метрики
    avg_order_value = (total_orders_amount / total_orders) if total_orders > 0 else 0
    cost_per_view = (total_amount / total_views) if total_views > 0 else 0
    cost_per_click = (total_amount / total_clicks) if total_clicks > 0 else 0
    cost_per_cart = (total_amount / total_atc) if total_atc > 0 else 0
    cpo = (total_amount / total_orders) if total_orders > 0 else 0
    
    # Норма ДРР - заглушка 10%
    norm_drr = 10.0
    
    # max Допустимый CPM рассчитывается как: avg_order_value * norm_drr / 100 * 1000
    # или можно рассчитать иначе, в зависимости от бизнес-логики
    max_cpm = (avg_order_value * norm_drr / 100) if avg_order_value > 0 else 0
    
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
    end_date: date
) -> List[Dict[str, Any]]:
    """
    Получить данные для графика динамики продвижения (CTR, CPM, сумма)
    
    Returns:
        List[Dict] с данными по дням:
        - date: Дата
        - ctr: CTR
        - cpm: CPM
        - amount: Сумма расходов
    """
    query = select(
        WbAdvertisingStats.date.label("date"),
        func.sum(WbAdvertisingStats.views).label("views"),
        func.sum(WbAdvertisingStats.clicks).label("clicks"),
        func.sum(WbAdvertisingStats.amount).label("amount"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    ).group_by(
        WbAdvertisingStats.date
    ).order_by(
        WbAdvertisingStats.date
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    data = []
    for row in rows:
        views = int(row.views or 0)
        clicks = int(row.clicks or 0)
        amount = float(row.amount or 0)
        
        ctr = (clicks / views * 100) if views > 0 else 0
        cpm = (amount / views * 1000) if views > 0 else 0
        
        data.append({
            "date": row.date.isoformat(),
            "ctr": round(ctr, 2),
            "cpm": round(cpm, 2),
            "amount": round(amount, 2),
        })
    
    return data


async def _get_articles_table(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """
    Получить данные для таблицы по артикулам
    
    Returns:
        List[Dict] с данными по каждому артикулу
    """
    query = select(
        WbAdvertisingStats.nm_id.label("nm_id"),
        WbAdvertisingStats.product_name.label("product_name"),
        func.sum(WbAdvertisingStats.views).label("total_views"),
        func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
        func.sum(WbAdvertisingStats.added_to_cart).label("total_atc"),
        func.sum(WbAdvertisingStats.orders).label("total_orders"),
        func.sum(WbAdvertisingStats.amount).label("total_amount"),
        func.sum(WbAdvertisingStats.orders_amount).label("total_orders_amount"),
        func.avg(WbAdvertisingStats.ctr).label("avg_ctr"),
        func.avg(WbAdvertisingStats.cr).label("avg_cr"),
        func.avg(WbAdvertisingStats.cpc).label("avg_cpc"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    ).group_by(
        WbAdvertisingStats.nm_id,
        WbAdvertisingStats.product_name
    ).order_by(
        func.sum(WbAdvertisingStats.amount).desc()
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    data = []
    for row in rows:
        views = int(row.total_views or 0)
        clicks = int(row.total_clicks or 0)
        atc = int(row.total_atc or 0)
        orders = int(row.total_orders or 0)
        amount = float(row.total_amount or 0)
        orders_amount = float(row.total_orders_amount or 0)
        
        # Рассчитываем дополнительные метрики
        ctr = float(row.avg_ctr or 0)
        cr = float(row.avg_cr or 0)
        cpc = float(row.avg_cpc or 0)
        
        # Конверсия из корзины в заказ
        cart_to_order = (orders / atc * 100) if atc > 0 else 0
        
        # Конверсия из перехода в заказ
        click_to_order = (orders / clicks * 100) if clicks > 0 else 0
        
        # Стоимость заказа в РК
        order_cost_in_ads = (amount / orders) if orders > 0 else 0
        
        # ДРР от общих заказов
        drr_from_orders = (amount / orders_amount * 100) if orders_amount > 0 else 0
        
        # CPM
        cpm = (amount / views * 1000) if views > 0 else 0
        
        data.append({
            "nm_id": row.nm_id,
            "product_name": row.product_name or "",
            "views": views,
            "clicks": clicks,
            "added_to_cart": atc,
            "ad_orders": orders,
            "ad_orders_amount": round(amount, 2),
            "total_orders": orders,  # Пока одинаково
            "total_orders_amount": round(orders_amount, 2),
            "expenses": round(amount, 2),
            "ctr": round(ctr, 2),
            "cr": round(cr, 2),
            "cart_to_order": round(cart_to_order, 2),
            "click_to_order": round(click_to_order, 2),
            "cpc": round(cpc, 2),
            "order_cost_in_ads": round(order_cost_in_ads, 2),
            "drr_from_orders": round(drr_from_orders, 2),
            "cpm": round(cpm, 2),
        })
    
    return data


@router.get('/', dependencies=[Depends(auth_middle)])
async def get_advertising_stats(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    Основной эндпоинт для страницы рекламной статистики
    
    Возвращает все данные для страницы:
    - funnel: Рекламная воронка
    - conversions: Конверсии по воронке
    - acquisition_cost: Расчет стоимости привлечения
    - dynamics_chart: Данные для графика динамики просмотров
    - promotion_dynamics: Данные для графика динамики продвижения (CTR, CPM, сумма)
    - articles_table: Таблица по артикулам
    """
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)
    
    current_user = request.state.user
    
    # Проверяем наличие активных токенов
    states = await get_user_sync_states(
        session=db_session,
        user_id=current_user['sub']
    )
    
    # Собираем ошибки синхронизации
    sync_errors = [s.last_error for s in states if s.last_error]
    auth_errors = [e for e in sync_errors if "401" in e or "403" in e or "Unauthorized" in e or "авторизации" in e.lower()]
    
    if auth_errors:
        logger.warning(f"User {current_user['sub']} has authorization errors in ads stats: {auth_errors}")
        return response_error(
            message="Ошибка авторизации: токен недействителен или истек срок действия. Пожалуйста, обновите токен в настройках.",
            code="TOKEN_INVALID"
        )
    
    user_tokens = await get_tokens_by_user_id(db_session, current_user['sub'])
    valid_wb_tokens = [
        t for t in user_tokens
        if t.marketplace == Marketplace.WILDBERRIES and t.is_valid
    ]
    
    if not valid_wb_tokens:
        return response_error(
            message="Нет действительных токенов для синхронизации. Пожалуйста, добавьте актуальный токен Wildberries.",
            code="NO_VALID_TOKENS"
        )
    
    # Получаем все данные параллельно
    funnel_data, conversion_data, acquisition_cost_data, dynamics_chart, promotion_dynamics, articles_table = await asyncio.gather(
        _get_funnel_data(db_session, current_user['sub'], start_date, end_date),
        _get_conversion_data(db_session, current_user['sub'], start_date, end_date),
        _get_acquisition_cost_data(db_session, current_user['sub'], start_date, end_date),
        get_advertising_stats_by_day(db_session, current_user['sub'], start_date, end_date),
        _get_promotion_dynamics(db_session, current_user['sub'], start_date, end_date),
        _get_articles_table(db_session, current_user['sub'], start_date, end_date),
    )
    
    return response_success(data={
        "funnel": funnel_data,
        "conversions": conversion_data,
        "acquisition_cost": acquisition_cost_data,
        "dynamics_chart": dynamics_chart,
        "promotion_dynamics": promotion_dynamics,
        "articles_table": articles_table,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    })
