from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from core.dependencies import get_db_session, require_permission
from core.logger import setup_logger
from core.middleware import auth_middle
from utils.responce_helps import response_error, response_success
from services.wb_product_services import (
    check_product_sync_status,
    get_products_count,
    get_total_stock_quantity,
    get_warehouse_stats,
    get_size_distribution,
    get_abc_analysis,
    get_top_products,
    get_selected_products,
    get_dashboard_stats,
    get_base_cabinet_stats,
    get_chart_data
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = setup_logger(__name__)


@router.get("/", dependencies=[Depends(auth_middle)])
async def dashboard(
    request: Request, 
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)

    current_user = request.state.user
    user_id = current_user['sub']

    # Проверяем наличие данных (синхронизированы ли товары)
    is_synced = await check_product_sync_status(
        session=db_session,
        user_id=user_id
    )

    if not is_synced:
        # Данные отсутствуют → не синхронизировано
        return response_error(
            message="Данные отсутствуют → не синхронизировано",
            code="NOT_DATA"
        )

    # Получаем статистику из БД
    stats = await get_dashboard_stats(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    # Получаем данные для графика
    chart_data = await get_chart_data(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    # Получаем основные показатели кабинета
    base_stats = await get_base_cabinet_stats(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    # Получаем данные по складам
    warehouse_data = await get_warehouse_stats(
        session=db_session,
        user_id=user_id
    )

    # Получаем ABC-анализ
    abc_analysis = await get_abc_analysis(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    # Получаем распределение по размерам
    size_chart = await get_size_distribution(
        session=db_session,
        user_id=user_id
    )

    # Получаем топ товаров для отображения
    selected_products = await get_selected_products(
        session=db_session,
        user_id=user_id,
        limit=4
    )

    # Получаем общее количество товаров и остатков
    products_count = await get_products_count(db_session, user_id)
    total_stock = await get_total_stock_quantity(db_session, user_id)

    return response_success(
        is_synced=is_synced,
        stats=stats.model_dump(),
        chartData=[item.model_dump() for item in chart_data],
        baseStats=base_stats.model_dump(),
        warehouseData=[item.model_dump() for item in warehouse_data],
        abcAnalysis=[item.model_dump() for item in abc_analysis],
        sizeChart=[item.model_dump() for item in size_chart],
        selectedProducts=[item.model_dump() for item in selected_products],
        products_count=products_count,
        total_stock=total_stock
    )
