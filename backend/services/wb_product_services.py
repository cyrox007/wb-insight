from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID as UUIDType

from sqlalchemy import func, select, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.wb_products import WbProduct, WbProductStock, ProductSyncLog
from schemas.products import (
    ProductListItemSchema,
    ProductWithStocksSchema,
    WarehouseStatSchema,
    SizeDistributionSchema,
    AbcAnalysisItemSchema,
    TopProductSchema,
    LowStockProductSchema,
    DashboardStatsSchema,
    MetricValueSchema,
    BaseCabinetStatsSchema,
    ChartDataPointSchema,
    SelectedProductSchema,
    SyncStatusSchema,
    SyncLogSchema
)


async def check_product_sync_status(
    session: AsyncSession, 
    user_id: UUIDType
) -> bool:
    """
    Проверка наличия товаров у пользователя.
    
    Returns:
        True если товары есть, иначе False
    """
    query = select(func.count(WbProduct.id)).where(
        WbProduct.user_id == user_id
    )
    
    result = await session.execute(query)
    count = result.scalar() or 0
    
    return count > 0


async def get_sync_status(
    session: AsyncSession,
    user_id: UUIDType
) -> SyncStatusSchema:
    """
    Получение статуса синхронизации пользователя.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        SyncStatusSchema со статусом синхронизации
    """
    # Проверяем наличие товаров
    products_query = select(func.count(WbProduct.id)).where(
        WbProduct.user_id == user_id
    )
    result = await session.execute(products_query)
    products_count = result.scalar() or 0
    
    is_synced = products_count > 0
    
    # Получаем последний лог синхронизации
    last_log = await get_last_sync_log(session, user_id)
    
    return SyncStatusSchema(
        is_synced=is_synced,
        last_sync_at=last_log.finished_at if last_log else None,
        last_sync_type=last_log.sync_type if last_log else None,
        last_sync_status=last_log.status if last_log else None,
        products_count=products_count,
        message="Данные синхронизированы" if is_synced else "Требуется синхронизация"
    )


async def get_products_count(
    session: AsyncSession,
    user_id: UUIDType,
    only_active: bool = True
) -> int:
    """
    Получение количества товаров пользователя.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        only_active: Только активные товары
        
    Returns:
        Количество товаров
    """
    query = select(func.count(WbProduct.id)).where(
        WbProduct.user_id == user_id
    )
    
    if only_active:
        query = query.where(WbProduct.is_active == True)
    
    result = await session.execute(query)
    return result.scalar() or 0


async def get_total_stock_quantity(
    session: AsyncSession,
    user_id: UUIDType
) -> int:
    """
    Получение общего количества товаров на складах.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        Общее количество товаров
    """
    query = select(func.coalesce(func.sum(WbProductStock.quantity), 0)).where(
        WbProductStock.user_id == user_id
    )
    
    result = await session.execute(query)
    return result.scalar() or 0


async def get_warehouse_stats(
    session: AsyncSession,
    user_id: UUIDType
) -> List[WarehouseStatSchema]:
    """
    Статистика по складам.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        Список WarehouseStatSchema со статистикой по каждому складу
    """
    query = select(
        WbProductStock.warehouse_name.label('name'),
        func.sum(WbProductStock.quantity).label('stock'),
        func.sum(WbProductStock.quantity_in_transit).label('in_transit'),
        func.sum(WbProductStock.quantity_reserved).label('reserved'),
        func.sum(WbProductStock.quantity_available).label('available')
    ).where(
        WbProductStock.user_id == user_id
    ).group_by(
        WbProductStock.warehouse_name
    ).order_by(
        func.sum(WbProductStock.quantity).desc()
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    return [
        WarehouseStatSchema(
            name=row.name,
            sum=row.stock or 0,
            stock=row.stock or 0,
            in_transit=row.in_transit or 0,
            reserved=row.reserved or 0,
            available=row.available or 0,
            goodsAmount=0.0
        )
        for row in rows
    ]


async def get_size_distribution(
    session: AsyncSession,
    user_id: UUIDType
) -> List[SizeDistributionSchema]:
    """
    Распределение товаров по размерам.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        Список SizeDistributionSchema с распределением по размерам
    """
    query = select(
        WbProduct.size.label('size'),
        func.sum(WbProductStock.quantity).label('quantity'),
        func.sum(WbProductStock.quantity_in_transit).label('inTransit')
    ).join(
        WbProductStock, WbProduct.id == WbProductStock.product_id
    ).where(
        WbProduct.user_id == user_id,
        WbProduct.size.isnot(None)
    ).group_by(
        WbProduct.size
    ).order_by(
        func.sum(WbProductStock.quantity).desc()
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    return [
        SizeDistributionSchema(
            size=row.size or 'N/A',
            quantity=row.quantity or 0,
            inTransit=row.inTransit or 0
        )
        for row in rows
    ]


async def get_abc_analysis(
    session: AsyncSession,
    user_id: UUIDType,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[AbcAnalysisItemSchema]:
    """
    ABC-анализ товаров по выручке.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        Список AbcAnalysisItemSchema с категориями A, B, C
    """
    from models.wb_report import WbRealizationReport
    
    # Запрос для получения выручки по товарам
    query = select(
        WbProduct.nm_id,
        WbProduct.vendor_code.label('seller_sku'),
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label('revenue'),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label('profit')
    ).join(
        WbRealizationReport, 
        WbProduct.nm_id == WbRealizationReport.nm_id,
        isouter=True
    ).where(
        WbProduct.user_id == user_id
    )
    
    if start_date:
        query = query.where(WbRealizationReport.rr_dt >= start_date)
    if end_date:
        query = query.where(WbRealizationReport.rr_dt <= end_date)
    
    query = query.group_by(
        WbProduct.nm_id, WbProduct.vendor_code
    ).order_by(
        func.sum(WbRealizationReport.retail_amount).desc()
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    # Расчёт совокупного процента и категорий ABC
    total_revenue = sum(float(row.revenue) for row in rows if row.revenue)
    
    abc_data = []
    cumulative = 0
    
    for row in rows:
        revenue = float(row.revenue) if row.revenue else 0
        profit = float(row.profit) if row.profit else 0
        
        share = (revenue / total_revenue * 100) if total_revenue > 0 else 0
        cumulative += share
        
        # Определение категории ABC
        if cumulative <= 80:
            category = 'A'
        elif cumulative <= 95:
            category = 'B'
        else:
            category = 'C'
        
        abc_data.append(AbcAnalysisItemSchema(
            id=row.nm_id,
            sellerSku=row.seller_sku or f'ART-{row.nm_id}',
            wbSku=str(row.nm_id),
            revenue=round(revenue, 2),
            profit=round(profit, 2),
            share=round(share, 1),
            cumulativePercent=round(cumulative, 1),
            category=category
        ))
    
    return abc_data


async def get_products_list(
    session: AsyncSession,
    user_id: UUIDType,
    limit: int = 100,
    offset: int = 0,
    only_active: bool = True
) -> List[ProductListItemSchema]:
    """
    Получение списка товаров пользователя.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        limit: Лимит записей
        offset: Смещение
        only_active: Только активные товары
        
    Returns:
        Список ProductListItemSchema
    """
    query = select(WbProduct).where(
        WbProduct.user_id == user_id
    )
    
    if only_active:
        query = query.where(WbProduct.is_active == True)
    
    query = query.order_by(
        WbProduct.total_revenue.desc().nullslast()
    ).limit(limit).offset(offset)
    
    result = await session.execute(query)
    products = result.scalars().all()
    
    return [
        ProductListItemSchema(
            id=product.id,
            nm_id=product.nm_id,
            vendor_code=product.vendor_code,
            name=product.name,
            brand=product.brand,
            category=product.category,
            sale_price=float(product.sale_price) if product.sale_price else None,
            retail_price=float(product.retail_price) if product.retail_price else None,
            discount_percent=float(product.discount_percent) if product.discount_percent else None,
            rating=float(product.rating) if product.rating else None,
            reviews_count=product.reviews_count,
            main_image_url=product.main_image_url,
            total_sales=product.total_sales,
            total_orders=product.total_orders,
            total_revenue=float(product.total_revenue) if product.total_revenue else None,
            is_active=product.is_active,
            created_at=product.created_at
        )
        for product in products
    ]


async def get_product_with_stocks(
    session: AsyncSession,
    user_id: UUIDType,
    product_id: UUIDType
) -> Optional[ProductWithStocksSchema]:
    """
    Получение товара с остатками по ID.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        product_id: ID товара
        
    Returns:
        ProductWithStocksSchema или None
    """
    query = select(WbProduct).options(
        joinedload(WbProduct.stocks)
    ).where(
        WbProduct.id == product_id,
        WbProduct.user_id == user_id
    )
    
    result = await session.execute(query)
    product = result.scalar_one_or_none()
    
    if not product:
        return None
    
    return ProductWithStocksSchema(
        id=product.id,
        user_id=product.user_id,
        nm_id=product.nm_id,
        vendor_code=product.vendor_code,
        barcode=product.barcode,
        name=product.name,
        brand=product.brand,
        category=product.category,
        subcategory=product.subcategory,
        description=product.description,
        retail_price=float(product.retail_price) if product.retail_price else None,
        sale_price=float(product.sale_price) if product.sale_price else None,
        discount_percent=float(product.discount_percent) if product.discount_percent else None,
        purchase_price=float(product.purchase_price) if product.purchase_price else None,
        vat_percent=float(product.vat_percent) if product.vat_percent else None,
        size=product.size,
        color=product.color,
        weight=product.weight,
        dimensions=product.dimensions,
        volume=float(product.volume) if product.volume else None,
        is_active=product.is_active,
        is_archived=product.is_archived,
        moderation_status=product.moderation_status,
        main_image_url=product.main_image_url,
        images_count=product.images_count,
        rating=float(product.rating) if product.rating else None,
        reviews_count=product.reviews_count,
        questions_count=product.questions_count,
        total_orders=product.total_orders,
        total_sales=product.total_sales,
        total_revenue=float(product.total_revenue) if product.total_revenue else None,
        created_at=product.created_at,
        updated_at=product.updated_at,
        first_sale_date=product.first_sale_date,
        last_sale_date=product.last_sale_date,
        stocks=[
            {
                'id': stock.id,
                'warehouse_name': stock.warehouse_name,
                'warehouse_id': stock.warehouse_id,
                'region': stock.region,
                'quantity': stock.quantity,
                'quantity_in_transit': stock.quantity_in_transit,
                'quantity_reserved': stock.quantity_reserved,
                'quantity_available': stock.quantity_available,
                'updated_at': stock.updated_at
            }
            for stock in product.stocks
        ]
    )


async def get_top_products(
    session: AsyncSession,
    user_id: UUIDType,
    limit: int = 10,
    by: str = 'revenue'
) -> List[TopProductSchema]:
    """
    Получение топ-N товаров по различным метрикам.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        limit: Количество товаров в топе
        by: Сортировка ('revenue', 'sales', 'orders', 'profit')
        
    Returns:
        Список TopProductSchema
    """
    order_column = {
        'revenue': WbProduct.total_revenue,
        'sales': WbProduct.total_sales,
        'orders': WbProduct.total_orders,
        'profit': WbProduct.total_revenue
    }.get(by, WbProduct.total_revenue)
    
    query = select(WbProduct).where(
        WbProduct.user_id == user_id,
        WbProduct.is_active == True
    ).order_by(
        order_column.desc().nullslast()
    ).limit(limit)
    
    result = await session.execute(query)
    products = result.scalars().all()
    
    return [
        TopProductSchema(
            id=product.nm_id,
            name=product.name,
            vendor_code=product.vendor_code,
            sale_price=float(product.sale_price) if product.sale_price else None,
            main_image_url=product.main_image_url,
            sales=product.total_sales,
            rating=float(product.rating) if product.rating else None,
            revenue=float(product.total_revenue) if product.total_revenue else None
        )
        for product in products
    ]


async def get_low_stock_products(
    session: AsyncSession,
    user_id: UUIDType,
    threshold: int = 10
) -> List[LowStockProductSchema]:
    """
    Получение товаров с низким остатком.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        threshold: Порог низкого остатка
        
    Returns:
        Список LowStockProductSchema
    """
    query = select(
        WbProduct,
        func.sum(WbProductStock.quantity).label('total_qty')
    ).join(
        WbProductStock, WbProduct.id == WbProductStock.product_id
    ).where(
        WbProduct.user_id == user_id,
        WbProduct.is_active == True
    ).group_by(
        WbProduct.id
    ).having(
        func.sum(WbProductStock.quantity) <= threshold
    ).order_by(
        func.sum(WbProductStock.quantity).asc()
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    return [
        LowStockProductSchema(
            id=product.nm_id,
            name=product.name,
            vendor_code=product.vendor_code,
            total_quantity=total_qty or 0,
            sale_price=float(product.sale_price) if product.sale_price else None
        )
        for product, total_qty in rows
    ]


async def get_dashboard_stats(
    session: AsyncSession,
    user_id: UUIDType,
    start_date: date,
    end_date: date
) -> DashboardStatsSchema:
    """
    Получение статистики для dashboard.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        DashboardStatsSchema со статистикой
    """
    from models.wb_report import WbOrderReport, WbRealizationReport
    
    # Базовые метрики из отчёта по заказам
    base_query = select(
        func.coalesce(func.sum(WbOrderReport.quantity), 0).label('ordered_units'),
        func.coalesce(func.sum(WbOrderReport.rp_with_disc), 0).label('ordered_amount')
    ).where(
        WbOrderReport.user_id == user_id,
        WbOrderReport.date >= start_date,
        WbOrderReport.date <= end_date
    )
    
    base_result = await session.execute(base_query)
    base_row = base_result.one()
    
    # Метрики из отчёта по продажам
    sales_query = select(
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label('sales_units'),
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label('sales_amount')
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )
    
    sales_result = await session.execute(sales_query)
    sales_row = sales_result.one()
    
    # Метрики из отчёта по возвратам
    returns_query = select(
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label('returns_units'),
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label('returns_amount')
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.return_status == 'Возврат'
    )
    
    returns_result = await session.execute(returns_query)
    returns_row = returns_result.one()
    
    # Расчёт метрик
    ordered_units = int(getattr(base_row, 'ordered_units', 0) or 0)
    ordered_amount = float(getattr(base_row, 'ordered_amount', 0) or 0)
    
    sales_units = int(getattr(sales_row, 'sales_units', 0) or 0)
    sales_amount = float(getattr(sales_row, 'sales_amount', 0) or 0)
    
    returns_units = int(getattr(returns_row, 'returns_units', 0) or 0)
    returns_amount = float(getattr(returns_row, 'returns_amount', 0) or 0)
    
    # Выручка = продажи - возвраты
    revenue = sales_amount - returns_amount
    
    # К перечислению (ppvz_for_pay)
    to_pay_query = select(
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0)
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )
    to_pay_result = await session.execute(to_pay_query)
    to_pay = float(to_pay_result.scalar() or 0)
    
    # Процент выкупа
    buyout_rate = (sales_units / ordered_units * 100) if ordered_units else 0.0
    
    # Средняя цена заказа
    avg_price = (ordered_amount / ordered_units) if ordered_units else 0.0
    
    # Прибыль (пока без учёта себестоимости)
    profit = to_pay
    
    return DashboardStatsSchema(
        ordered_amount=MetricValueSchema(value=round(ordered_amount, 2)),
        ordered_units=MetricValueSchema(value=ordered_units),
        revenue=MetricValueSchema(value=round(revenue, 2)),
        sold_units=MetricValueSchema(value=sales_units),
        to_pay=MetricValueSchema(value=round(to_pay, 2)),
        profit=MetricValueSchema(value=round(profit, 2)),
        buyout_rate=MetricValueSchema(value=round(buyout_rate, 1)),
        avg_price=MetricValueSchema(value=round(avg_price, 2))
    )


async def get_base_cabinet_stats(
    session: AsyncSession,
    user_id: UUIDType,
    start_date: date,
    end_date: date
) -> BaseCabinetStatsSchema:
    """
    Получение основных показателей кабинета.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        BaseCabinetStatsSchema с показателями
    """
    from models.wb_report import WbOrderReport, WbRealizationReport, WbAdvertisementReport
    
    # Запрос к рекламе
    ad_query = select(
        func.coalesce(func.sum(WbAdvertisementReport.views), 0).label('adViews'),
        func.coalesce(func.sum(WbAdvertisementReport.clicks), 0).label('clicks')
    ).where(
        WbAdvertisementReport.user_id == user_id,
        WbAdvertisementReport.date >= start_date,
        WbAdvertisementReport.date <= end_date
    )
    
    ad_result = await session.execute(ad_query)
    ad_row = ad_result.one()
    
    ad_views = int(getattr(ad_row, 'adViews', 0) or 0)
    clicks = int(getattr(ad_row, 'clicks', 0) or 0)
    clicks_percentage = (clicks / ad_views * 100) if ad_views else 0.0
    
    # Заказы
    orders_query = select(
        func.coalesce(func.sum(WbOrderReport.quantity), 0).label('orderedTotalCount'),
        func.coalesce(func.sum(WbOrderReport.rp_with_disc), 0).label('orderedTotalAmount')
    ).where(
        WbOrderReport.user_id == user_id,
        WbOrderReport.date >= start_date,
        WbOrderReport.date <= end_date
    )
    
    orders_result = await session.execute(orders_query)
    orders_row = orders_result.one()
    
    ordered_total_count = int(getattr(orders_row, 'orderedTotalCount', 0) or 0)
    ordered_total_amount = float(getattr(orders_row, 'orderedTotalAmount', 0) or 0)
    
    # Продажи
    sales_query = select(
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label('boughtTotalCount'),
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label('boughtTotalAmount'),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label('profit')
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )
    
    sales_result = await session.execute(sales_query)
    sales_row = sales_result.one()
    
    bought_total_count = int(getattr(sales_row, 'boughtTotalCount', 0) or 0)
    bought_total_amount = float(getattr(sales_row, 'boughtTotalAmount', 0) or 0)
    profit = float(getattr(sales_row, 'profit', 0) or 0)
    
    buyout_percent = (bought_total_count / ordered_total_count * 100) if ordered_total_count else 0.0
    avg_order_value = (ordered_total_amount / ordered_total_count) if ordered_total_count else 0.0
    
    # Маржинальность и доля расходов (расчётные)
    marginality = (profit / bought_total_amount * 100) if bought_total_amount else 0.0
    expense_ratio = 100 - marginality
    
    return BaseCabinetStatsSchema(
        adViews=ad_views,
        clicks=clicks,
        clicksPercentage=round(clicks_percentage, 1),
        addToCart=0,  # пока нет данных
        addToCartPercentage=0.0,
        orderedTotalCount=ordered_total_count,
        orderedTotalAmount=ordered_total_amount,
        boughtTotalCount=bought_total_count,
        boughtTotalAmount=bought_total_amount,
        buyoutPercent=round(buyout_percent, 2),
        avgOrderValue=round(avg_order_value, 2),
        marginality=round(marginality, 1),
        expenseRatio=round(expense_ratio, 1),
        profit=round(profit, 2),
        revenue=bought_total_amount,
        logistics=0.0,  # пока нет данных
        storage=0.0
    )


async def get_chart_data(
    session: AsyncSession,
    user_id: UUIDType,
    start_date: date,
    end_date: date
) -> List[ChartDataPointSchema]:
    """
    Получение данных для графика по дням.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        Список ChartDataPointSchema для графика
    """
    from models.wb_report import WbOrderReport, WbRealizationReport
    
    # Группировка по датам
    query = select(
        WbOrderReport.date.label('date'),
        func.coalesce(func.sum(WbOrderReport.rp_with_disc), 0).label('orders'),
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label('buyouts'),
        func.coalesce(func.avg(WbOrderReport.rp_with_disc), 0).label('avg_price'),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label('profit')
    ).join(
        WbRealizationReport,
        and_(
            WbOrderReport.nm_id == WbRealizationReport.nm_id,
            WbOrderReport.date == WbRealizationReport.rr_dt
        ),
        isouter=True
    ).where(
        WbOrderReport.user_id == user_id,
        WbOrderReport.date >= start_date,
        WbOrderReport.date <= end_date
    ).group_by(
        WbOrderReport.date
    ).order_by(
        WbOrderReport.date
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    chart_data = []
    for row in rows:
        orders = float(getattr(row, 'orders', 0) or 0)
        buyouts = float(getattr(row, 'buyouts', 0) or 0)
        avg_price = float(getattr(row, 'avg_price', 0) or 0)
        profit = float(getattr(row, 'profit', 0) or 0)
        
        # Расчёт маржинальности
        margin = (profit / buyouts * 100) if buyouts else 0.0
        
        chart_data.append(ChartDataPointSchema(
            date=getattr(row, 'date').strftime('%d.%m'),
            orders=round(orders, 2),
            buyouts=round(buyouts, 2),
            avg_price=round(avg_price, 2),
            profit=round(profit, 2),
            margin=round(margin, 1),
            views=0,  # пока нет данных
            clicks=0,
            cart=0,
            cr=0.0,
            ctr=0.0,
            drr=0.0
        ))
    
    return chart_data


async def get_selected_products(
    session: AsyncSession,
    user_id: UUIDType,
    limit: int = 4
) -> List[SelectedProductSchema]:
    """
    Получение выбранных товаров для отображения.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        limit: Количество товаров
        
    Returns:
        Список SelectedProductSchema
    """
    query = select(WbProduct).where(
        WbProduct.user_id == user_id,
        WbProduct.is_active == True,
        WbProduct.main_image_url.isnot(None)
    ).order_by(
        WbProduct.total_sales.desc()
    ).limit(limit)
    
    result = await session.execute(query)
    products = result.scalars().all()
    
    return [
        SelectedProductSchema(
            id=product.nm_id,
            name=product.name,
            price=f"{int(product.sale_price):,}" if product.sale_price else "0",
            image=product.main_image_url or "",
            sales=product.total_sales,
            rating=float(product.rating) if product.rating else 0.0
        )
        for product in products
    ]


async def get_last_sync_log(
    session: AsyncSession,
    user_id: UUIDType
) -> Optional[ProductSyncLog]:
    """
    Получение последнего лога синхронизации.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        Последний лог синхронизации или None
    """
    query = select(ProductSyncLog).where(
        ProductSyncLog.user_id == user_id
    ).order_by(
        ProductSyncLog.started_at.desc()
    ).limit(1)
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_sync_log(
    session: AsyncSession,
    user_id: UUIDType,
    sync_type: str = "full",
    source: str = "emulation"
) -> ProductSyncLog:
    """
    Создание лога синхронизации.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        sync_type: Тип синхронизации
        source: Источник данных
        
    Returns:
        Созданный лог синхронизации
    """
    sync_log = ProductSyncLog(
        user_id=user_id,
        sync_type=sync_type,
        status="in_progress",
        source=source
    )
    session.add(sync_log)
    await session.flush()
    
    return sync_log


async def update_sync_log_success(
    session: AsyncSession,
    sync_log: ProductSyncLog,
    products_loaded: int = 0,
    products_created: int = 0,
    products_updated: int = 0,
    products_deleted: int = 0,
    stocks_processed: int = 0
):
    """
    Обновление лога синхронизации при успешном завершении.
    """
    sync_log.status = "success"
    sync_log.products_loaded = products_loaded
    sync_log.products_created = products_created
    sync_log.products_updated = products_updated
    sync_log.products_deleted = products_deleted
    sync_log.stocks_processed = stocks_processed
    sync_log.errors_count = 0
    sync_log.finished_at = datetime.now(timezone.utc)
    sync_log.duration_seconds = (sync_log.finished_at - sync_log.started_at).total_seconds()
    
    await session.commit()


async def update_sync_log_error(
    session: AsyncSession,
    sync_log: ProductSyncLog,
    error_message: str,
    error_details: Optional[str] = None
):
    """
    Обновление лога синхронизации при ошибке.
    """
    sync_log.status = "failed"
    sync_log.error_message = error_message
    sync_log.error_details = error_details
    sync_log.finished_at = datetime.now(timezone.utc)
    sync_log.duration_seconds = (sync_log.finished_at - sync_log.started_at).total_seconds()
    
    await session.commit()
