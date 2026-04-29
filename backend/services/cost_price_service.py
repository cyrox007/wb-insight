from datetime import date, datetime, timezone
from uuid import UUID
from typing import List, Optional, Tuple

from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.product_cost_price_model import ProductCostPrice
from models.wb_report import WbRealizationReport
from schemas.cost_price import UnitEconomyMetrics

async def get_or_cost_price(session: AsyncSession, user_id: UUID, nm_id: int) -> Optional[ProductCostPrice]:
    """ Получить себестоимость товара или None если не найдена """
    query = select(ProductCostPrice).where(
        ProductCostPrice.user_id == user_id,
        ProductCostPrice.nm_id == nm_id
    )

    result = await session.execute(query)
    return result.scalar_one_or_none()


async def upsert_cost_prices(session: AsyncSession, user_id: UUID, items: list[dict]) -> int:
    values = []
    for item in items:
        values.append({
            'user_id': user_id,
            'nm_id': item['nm_id'],
            'seller_sku': item['seller_sku'],
            'product_name': item['product_name'],
            'cost_price': item['cost_price'],
            'currency': item['currency'],
            'comment': item['comment'],
            'updated_at': datetime.now(timezone.utc),
            'created_at': datetime.now(timezone.utc),
        })

    if not values:
        return 0

    # INSERT ... ON CONFLICT DO UPDATE
    stmt = insert(ProductCostPrice).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['user_id', 'nm_id'],
        set_={
            'seller_sku': stmt.excluded.seller_sku,
            'product_name': stmt.excluded.product_name,
            'cost_price': stmt.excluded.cost_price,
            'currency': stmt.excluded.currency,
            'comment': stmt.excluded.comment,
            'updated_at': func.now(),
        }
    )

    stmt = stmt.returning(ProductCostPrice.nm_id)

    result = await session.execute(stmt)
    rows = result.fetchall()
    return len(rows)

async def calculate_unit_economy(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    nm_id: Optional[int] = None
) -> Optional[dict]:
    """ Расчёт метрик unit-экономики для товара или всех товаров """
    # Базовый запрос к отчётам
    base_query = select(
        func.sum(WbRealizationReport.retail_amount).label('revenue'),
        func.sum(WbRealizationReport.quantity).label('total_quantity'),
        func.sum(WbRealizationReport.ppvz_for_pay).label('payout'),
        func.sum(WbRealizationReport.ppvz_sales_commission).label('commission'),
        func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub).label('logistics'),
        func.sum(WbRealizationReport.penalty).label('penalty'),
        func.sum(WbRealizationReport.storage_fee).label('storage'),
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name.in_(['Продажа', 'Возврат'])
    )

    if nm_id:
        base_query = base_query.where(WbRealizationReport.nm_id == nm_id)

    base_result = await session.execute(base_query)
    base_row = base_result.fetchone()

    if not base_row or not base_row.revenue or float(base_row.revenue) == 0:
        return None

    revenue = float(base_row.revenue or 0)
    total_quantity = int(base_row.total_quantity or 0)
    payout = float(base_row.payout or 0)
    commission = float(base_row.commission or 0)
    logistics = float(base_row.logistics or 0)
    penalty = float(base_row.penalty or 0)
    storage = float(base_row.storage or 0)

    # Запрос себестоимости
    cost_query = select(
        WbRealizationReport.nm_id,
        func.sum(WbRealizationReport.quantity).label('qty'),
        ProductCostPrice.cost_price
    ).join(
        ProductCostPrice,
        ProductCostPrice.nm_id == WbRealizationReport.nm_id,
        isouter=True
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        ProductCostPrice.user_id == user_id
    )

    if nm_id:
        cost_query = cost_query.where(WbRealizationReport.nm_id == nm_id)

    cost_query = cost_query.group_by(WbRealizationReport.nm_id, ProductCostPrice.cost_price)
    cost_result = await session.execute(cost_query)
    cost_rows = cost_result.fetchall()

    # Расчёт общей себестоимости
    total_cost = 0.0
    for row in cost_rows:
        qty = int(row.qty or 0)
        cost = float(row.cost_price) if row.cost_price else 0.0
        total_cost += cost * qty

    # Прибыль = к выплате - себестоимость
    profit = payout - total_cost

    # Маржинальность = (прибыль / выручка) × 100
    margin_percent = (profit / revenue * 100) if revenue > 0 else 0.0

    # DRR = ((комиссия + логистика + штрафы) / выручка) × 100
    drr_percent = ((commission + logistics + penalty) / revenue * 100) if revenue > 0 else 0.0

    # Рентабельность = (прибыль / к выплате) × 100
    profitability_percent = (profit / payout * 100) if payout > 0 else 0.0

    return {
        'revenue': round(revenue, 2),
        'total_cost': round(total_cost, 2),
        'payout': round(payout, 2),
        'commission': round(commission, 2),
        'logistics': round(logistics, 2),
        'penalty': round(penalty, 2),
        'storage': round(storage, 2),
        'profit': round(profit, 2),
        'margin_percent': round(margin_percent, 2),
        'drr_percent': round(drr_percent, 2),
        'profitability_percent': round(profitability_percent, 2)
    }

async def get_dashboard_unit_economy(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> dict:
    """ Агрегированные метрики unit-экономики для дашборда """
    metrics = await calculate_unit_economy(session, user_id, start_date, end_date)
    if not metrics:
        return {
            'total_revenue': 0.0,
            'total_cost': 0.0,
            'total_profit': 0.0,
            'avg_margin_percent': 0.0,
            'avg_drr_percent':0.0,
            'products_with_cost': 0,
            'products_without_cost':0
        }
    
    # Подсчёт товаров с себестоимостью и без
    query = select(
        func.count(func.distinct(WbRealizationReport.nm_id)).label("total"),
        func.count(func.distinct(ProductCostPrice.nm_id)).label("with_cost")
    ).select_from(WbRealizationReport).join(
        ProductCostPrice,
        (ProductCostPrice.nm_id == WbRealizationReport.nm_id) &
        (ProductCostPrice.user_id == user_id),
        isouter=True
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )

    result = await session.execute(query)
    row = result.one()

    products_with_cost = row.with_cost or 0
    products_total = row.total or 0
    products_without_cost = products_total - products_with_cost
    return {
        'total_revenue': metrics.get('revenue', 0.0),
        'total_cost': metrics.get('total_cost', 0.0),
        'total_profit': metrics.get('profit', 0.0),
        'avg_margin_percent': metrics.get('margin_percent', 0.0),
        'avg_drr_percent':metrics.get('drr_percent', 0.0),
        'products_with_cost': products_with_cost,
        'products_without_cost': products_without_cost
    }


async def get_product_list_with_costs(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[dict], int]:
    """ Получить список товаров с метриками и себестоимостью """
    # Получаем агрегацию по товарам
    query = select(
        WbRealizationReport.nm_id,
        func.max(WbRealizationReport.sa_name).label('seller_sku'),
        func.max(WbRealizationReport.brand_name).label('brand'),
        func.max(WbRealizationReport.title).label('product_name'),
        func.sum(WbRealizationReport.retail_amount).label('revenue'),
        func.sum(WbRealizationReport.quantity).label('quantity'),
        func.sum(WbRealizationReport.ppvz_for_pay).label('payout'),
        func.sum(WbRealizationReport.ppvz_sales_commission).label('commission'),
        func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub).label('logistics'),
        func.sum(WbRealizationReport.penalty).label('penalty'),
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name.in_(['Продажа', 'Возврат'])
    ).group_by(
        WbRealizationReport.nm_id
    ).order_by(
        func.sum(WbRealizationReport.retail_amount).desc()
    ).limit(limit).offset(offset)

    result = await session.execute(query)
    rows = result.fetchall()

    # Получаем себестоимость для этих товаров
    nm_ids = [row.nm_id for row in rows]
    cost_query = select(ProductCostPrice).where(
        ProductCostPrice.user_id == user_id,
        ProductCostPrice.nm_id.in_(nm_ids)
    )
    cost_result = await session.execute(cost_query)
    costs = {row.nm_id: row.cost_price for row in cost_result.scalars().all()}

    # Формируем ответ
    products = []
    for row in rows:
        cost = costs.get(row.nm_id, 0.0)
        total_cost = cost * int(row.quantity or 0)
        profit = float(row.payout or 0) - total_cost
        revenue = float(row.revenue or 0)
        margin = (profit / revenue * 100) if revenue > 0 else 0.0
        drr = ((float(row.commission or 0) + float(row.logistics or 0) + float(row.penalty or 0)) / revenue * 100) if revenue > 0 else 0.0

        products.append({
            'nm_id': row.nm_id,
            'seller_sku': row.seller_sku,
            'brand': row.brand,
            'product_name': row.product_name,
            'revenue': round(revenue, 2),
            'quantity': int(row.quantity or 0),
            'cost_price': cost,
            'total_cost': round(total_cost, 2),
            'payout': round(float(row.payout or 0), 2),
            'profit': round(profit, 2),
            'margin_percent': round(margin, 2),
            'drr_percent': round(drr, 2),
            'has_cost': row.nm_id in costs
        })

    # Общее количество
    count_query = select(func.count(func.distinct(WbRealizationReport.nm_id))).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )
    count_result = await session.execute(count_query)
    total_count = count_result.scalar() or 0

    return products, total_count