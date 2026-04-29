from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from core.dependencies import get_db_session, require_permission
from core.logger import setup_logger
from core.middleware import auth_middle
from utils.responce_helps import response_error, response_success
from services.wb_report_service import check_wb_report_stats, get_base_wb_report_stats, get_returns_wb_report_stats, get_sales_wb_report_stats
from services.cost_price_service import get_dashboard_unit_economy

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

    # print(request.state.user)
    current_user = request.state.user

    report_count = await check_wb_report_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )

    if report_count == 0:
        # Данные отсутствуют → не синхронизировано
        return response_error(
            message="Данные отсутствуют → не синхронизировано",
            code="NOT_DATA"
        )

    # Выполняем запросы
    base_result = await get_base_wb_report_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )

    sales_result = await get_sales_wb_report_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )
    returns_result = await get_returns_wb_report_stats(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )

    # Расчёт метрик
    ordered_amount = float(getattr(base_result, 'ordered_amount', 0) or 0)
    ordered_units = int(getattr(base_result, 'ordered_units', 0) or 0)
    
    sales_amount = float(getattr(sales_result, 'sales_amount', 0) or 0)
    sales_units = int(getattr(sales_result, 'sales_units', 0) or 0)
    
    returns_amount = float(getattr(returns_result, 'returns_amount', 0) or 0)
    returns_units = int(getattr(returns_result, 'returns_units', 0) or 0)

    # Выручка = продажи - возвраты
    revenue = sales_amount - returns_amount
    
    # К перечислению (уже агрегировано в ppvz_for_pay)
    to_pay = float(getattr(base_result, 'to_pay', 0) or 0)
    
    # К выплате = к перечислению - комиссия - логистика - штрафы - прочие - хранение
    # (в реальности это уже учтено в ppvz_for_pay, но для расчёта прибыли нужно вычесть себестоимость)
    payout = to_pay
    
    # Процент выкупа
    buyout_rate = (sales_units / ordered_units * 100) if ordered_units else 0.0
    
    # Средняя цена заказа
    avg_price = (ordered_amount / ordered_units) if ordered_units else 0.0

    # Расчёт unit-экономики с учётом себестоимости
    unit_economy = await get_dashboard_unit_economy(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date
    )
    
    # Прибыль = к выплате - себестоимость
    profit = unit_economy['total_profit']
    # Маржинальность % = (прибыль / выручка) × 100
    marginality = unit_economy['avg_margin_percent']
    # Рентабельность % = (прибыль / к выплате) × 100
    profitability = (profit / to_pay * 100) if to_pay > 0 else 0.0
    # DRR = доля расходов от продаж
    ddr = unit_economy['avg_drr_percent']

    # Статистика (пример)
    stats = {
        "ordered_amount": {
            "value": round(ordered_amount, 2),
            "change_percent": 0.0,  # пока без сравнения с предыдущим периодом
            "change_abs": 0.0
        },
        "ordered_units": {
            "value": ordered_units,
            "change_percent": 0.0,
            "change_abs": 0
        },
        "revenue": {
            "value": round(revenue, 2),
            "change_percent": 0.0,
            "change_abs": 0.0
        },
        "sold_units": {
            "value": sales_units,
            "change_percent": 0.0,
            "change_abs": 0
        },
        "to_pay": {
            "value": round(to_pay, 2),
            "change_percent": 0.0,
            "change_abs": 0.0
        },
        "profit": {
            "value": round(profit, 2),
            "change_percent": 0.0,
            "change_abs": 0.0
        },
        "buyout_rate": {
            "value": round(buyout_rate, 1),
            "change_percent": 0.0,
            "change_abs": 0.0
        },
        "avg_price": {
            "value": round(avg_price, 2),
            "change_percent": 0.0,
            "change_abs": 0.0
        },
        "marginality": {
            "value": round(marginality, 1) if marginality else 0.0
        },
        "profitability": {
            "value": round(profitability, 1) if profitability else 0.0
        },
        "ddr": {
            "value": round(ddr, 2) if ddr else 0.0
        },
        "fact_current_month": {
            "value": round(0.00, 2)
        },
        "plan_current_month": {
            "value": round(50000000, 2)
        },
        "done": {
            "value": round(0.0, 2)
        },
        "forecast": {
            "value": round(27, 0)
        },
        "recommended_orders_per_day": {
            "value": round(166593.73, 2)
        }
    }
    
    # данные для графика (пример)
    chartData = [{
		'date': '01.09',
		'orders': 880000,
		'buyouts': 380000,
		'avg_price': 15921.64,
		'profit': -10000,
		'margin': -2.7,
		'views': 67934,
		'clicks': 3120,
		'cart': 200,
		'cr': 6.5,
		'ctr': 4.6,
		'drr': 1.4
	},
	{
		'date': '02.09',
		'orders': 950000,
		'buyouts': 410000,
		'avg_price': 16250.00,
		'profit': -8000,
		'margin': -2.5,
		'views': 72345,
		'clicks': 3345,
		'cart': 215,
		'cr': 6.3,
		'ctr': 4.5,
		'drr': 1.3
	},
	{
		'date': '03.09',
		'orders': 820000,
		'buyouts': 350000,
		'avg_price': 14890.50,
		'profit': -12000,
		'margin': -3.0,
		'views': 58923,
		'clicks': 2890,
		'cart': 185,
		'cr': 6.0,
		'ctr': 4.4,
		'drr': 1.5
	},
	{
		'date': '04.09',
		'orders': 780000,
		'buyouts': 320000,
		'avg_price': 14320.75,
		'profit': -15000,
		'margin': -3.5,
		'views': 54120,
		'clicks': 2650,
		'cart': 170,
		'cr': 5.8,
		'ctr': 4.3,
		'drr': 1.6
	},
	{
		'date': '05.09',
		'orders': 890000,
		'buyouts': 400000,
		'avg_price': 15500.00,
		'profit': -9000,
		'margin': -2.8,
		'views': 65432,
		'clicks': 3080,
		'cart': 195,
		'cr': 6.2,
		'ctr': 4.5,
		'drr': 1.4
	},
	{
		'date': '06.09',
		'orders': 920000,
		'buyouts': 420000,
		'avg_price': 16340.25,
		'profit': -7000,
		'margin': -2.3,
		'views': 70123,
		'clicks': 3250,
		'cart': 210,
		'cr': 6.4,
		'ctr': 4.6,
		'drr': 1.3
	},
	{
		'date': '07.09',
		'orders': 860000,
		'buyouts': 390000,
		'avg_price': 15210.80,
		'profit': -11000,
		'margin': -3.1,
		'views': 63210,
		'clicks': 2980,
		'cart': 188,
		'cr': 5.9,
		'ctr': 4.3,
		'drr': 1.5
	}]

    # основные показатели по кабинету пример
    base_stats = {
        # Первая группа
        'adViews': 1843682,           # Просмотры Рекламы
        'clicks': 78014,              # Клики
        'clicksPercentage': 4.2,      # % кликов от просмотров
        'addToCart': 6378,            # Добавлено в корзину
        'addToCartPercentage': 8.2,   # % добавлений от кликов

        # Вторая группа
        'orderedTotalCount': 3105,    # Заказано всего (количество)
        'orderedTotalAmount': 36589404.10, # Заказано всего (сумма)
        'boughtTotalCount': 2852,     # Выкуплено всего (количество)
        'boughtTotalAmount': 14255887.40,  # Выкуплено всего (сумма)
        'buyoutPercent': 1.08,        # Процент выкупа

        # Третья группа
        'avgOrderValue': 4999.63,     # Средняя стоимость заказа
        'marginality': 16.6,          # Маржинальность (%)
        'expenseRatio': 83.4,         # Доля расходов от продаж (%)
        'profit': 2335140.60,         # Прибыль
        'revenue': 36589404.10,       # Выручка
        'logistics': 3345000.00,      # Логистика
        'storage': 55000.00           # Хранение
    }

    warehouseData = [
        { 'name': 'Тула', sum: 771, 'stock': 2722, 'goodsAmount': 0 },
        { 'name': 'Электросталь', sum: 771, 'stock': 2431, 'goodsAmount': 0 },
        { 'name': 'Коледино', sum: 885, 'stock': 1323, 'goodsAmount': 0 },
        { 'name': 'Краснодар', sum: 576, 'stock': 1239, 'goodsAmount': 0 },
        { 'name': 'Казань', sum: 309, 'stock': 838, 'goodsAmount': 0 },
        { 'name': 'Рязань (Тюшевское)', sum: 122, 'stock': 746, 'goodsAmount': 0 },
        { 'name': 'Невинномысск', sum: 227, 'stock': 550, 'goodsAmount': 0 },
        { 'name': 'Екатеринбург - Испытателей 14г', sum: 174, 'stock': 473, 'goodsAmount': 0 },
        { 'name': 'Самара (Новосемейкино)', sum: 268, 'stock': 460, 'goodsAmount': 0 },
        { 'name': 'Санкт-Петербург Уткина Заводь', sum: 66, 'stock': 388, 'goodsAmount': 0 },
        { 'name': 'Новосибирск', sum: 136, 'stock': 259, 'goodsAmount': 0 },
        { 'name': 'Котовск', sum: 58, 'stock': 157, 'goodsAmount': 0 },
        { 'name': 'Владимир', sum: 75, 'stock': 124, 'goodsAmount': 0 },
        { 'name': 'Волгоград', sum: 69, 'stock': 122, 'goodsAmount': 0 },
        { 'name': 'Воронеж', sum: 32, 'stock': 105, 'goodsAmount': 0 },
        { 'name': 'Сарапул', sum: 115, 'stock': 74, 'goodsAmount': 0 },
        { 'name': 'Екатеринбург - Перспективный 12', sum: 233, 'stock': 52, 'goodsAmount': 0 },
        { 'name': 'Астана Карагандинское шоссе', sum: 19, 'stock': 15, 'goodsAmount': 0 },
        { 'name': 'Белая дача', sum: 11, 'stock': 15, 'goodsAmount': 0 },
        { 'name': 'Актобе', sum: 2, 'stock': 13, 'goodsAmount': 0 },
        { 'name': 'Атакент', sum: 10, 'stock': 8, 'goodsAmount': 0 },
        { 'name': 'Калининград', sum: 7, 'stock': 7, 'goodsAmount': 0 },
        { 'name': 'СЦ Ереван', sum: 6, 'stock': 5, 'goodsAmount': 0 },
        { 'name': 'Чашниково', sum: 2, 'stock': 3, 'goodsAmount': 0 },
        { 'name': 'Обухово', sum: 2, 'stock': 1, 'goodsAmount': 0 },
        { 'name': 'СЦ Барнаул', sum: 10, 'stock': 1, 'goodsAmount': 0 },
    ]

    # пример данных для таблицы ABC анализа
    abcAnalysis = [
        {
            "id": 12345,              # Уникальный ID для key в v-for
            "sellerSku": "ART-001",   # Артикул продавца (строка)
            "wbSku": "12345678",      # Артикул WB (строка, может быть null)
            "revenue": 150000,        # Выручка (число)
            "profit": 45000,          # Прибыль (число)
            "share": 12.5,            # Доля в выручке (число, %)
            "cumulativePercent": 45.2,# Совокупный процент (число, %)
            "category": "A"           # Категория (строка: "A", "B" или "C")
        },
        { 'id': 1, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '182440753', 'revenue': 624572.9, 'profit': 348148.4, 'share': 22.8, 'cumulativePercent': 22.8, 'category': 'A' },
	    { 'id': 2, 'sellerSku': 'РубашкаШелк-01-зп', 'wbSku': '152048084', 'revenue': 324707.9, 'profit': 172073.6, 'share': 11.3, 'cumulativePercent': 34.1, 'category': 'A' },
	    { 'id': 3, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '219169078', 'revenue': 208559.2, 'profit': 143802.8, 'share': 9.4, 'cumulativePercent': 43.6, 'category': 'A' },
	    { 'id': 4, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '190442797', 'revenue': 189835.0, 'profit': 111008.8, 'share': 7.3, 'cumulativePercent': 50.9, 'category': 'A' },
	    { 'id': 5, 'sellerSku': 'ВолнистаяБлузка-0', 'wbSku': '388639444', 'revenue': 177276.6, 'profit': 99807.4, 'share': 6.5, 'cumulativePercent': 57.4, 'category': 'A' },
	    { 'id': 6, 'sellerSku': 'ПлатьеОдноПлехо-1', 'wbSku': '391354791', 'revenue': 214603.6, 'profit': 91153.8, 'share': 6.0, 'cumulativePercent': 63.4, 'category': 'A' },
	    { 'id': 7, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '334837164', 'revenue': 120756.0, 'profit': 84180.7, 'share': 5.5, 'cumulativePercent': 68.9, 'category': 'A' },
	    { 'id': 8, 'sellerSku': 'РубашкаШелк-01-ч', 'wbSku': '144826387', 'revenue': 138890.4, 'profit': 80063.8, 'share': 5.3, 'cumulativePercent': 74.2, 'category': 'A' },
	    { 'id': 9, 'sellerSku': 'БлузкаПланка-01-б', 'wbSku': '104098349', 'revenue': 100457.5, 'profit': 66591.8, 'share': 4.4, 'cumulativePercent': 78.5, 'category': 'B' },
	    { 'id': 10, 'sellerSku': 'ПальтоХалатДрап-С', 'wbSku': '170206280', 'revenue': 114379.2, 'profit': 58267.9, 'share': 3.8, 'cumulativePercent': 82.3, 'category': 'B' }
    ]

    categoryData = [
        { "category": 'Блузки', 'value': 2574164 },
        { "category": 'Пальто', 'value': 1282464 },
        { "category": 'Платья', 'value': 1047567 },
        { "category": 'Пуховики', 'value': 41436 },
        { "category": 'Рубашки', 'value': 5504988 }
    ]

    products = [
        { 'id': 1, 'name': 'Электросталь', 'sales': 2722, 'profit': 1500 },
        { 'id': 2, 'name': 'Коледино', 'sales': 1323, 'profit': 800 },
        { 'id': 3, 'name': 'Казань', 'sales': 638, 'profit': 400 },
        { 'id': 4, 'name': 'Рязань', 'sales': 746, 'profit': 500 },
        { 'id': 5, 'name': 'Невинномысск', 'sales': 550, 'profit': 300 },
        { 'id': 6, 'name': 'Екатеринбург', 'sales': 473, 'profit': 250 },
        { 'id': 7, 'name': 'Самара', 'sales': 460, 'profit': 200 },
        { 'id': 8, 'name': 'Санкт-Петербург', 'sales': 388, 'profit': 180 },
        { 'id': 9, 'name': 'Новосибирск', 'sales': 259, 'profit': 150 },
        { 'id': 10, 'name': 'Котовск', 'sales': 157, 'profit': 100 },
        { 'id': 11, 'name': 'Владимир', 'sales': 124, 'profit': 80 },
        { 'id': 12, 'name': 'Волгоград', 'sales': 122, 'profit': 70 },
        { 'id': 13, 'name': 'Воронеж', 'sales': 105, 'profit': 60 },
        { 'id': 14, 'name': 'Саратов', 'sales': 74, 'profit': 40 },
        { 'id': 15, 'name': 'Екатеринбург', 'sales': 52, 'profit': 30 },
        { 'id': 16, 'name': 'Астана', 'sales': 15, 'profit': 10 },
        { 'id': 17, 'name': 'Белая дача', 'sales': 15, 'profit': 10 },
        { 'id': 18, 'name': 'Актобе', 'sales': 13, 'profit': 8 },
        { 'id': 19, 'name': 'Атакент', 'sales': 8, 'profit': 5 },
        { 'id': 20, 'name': 'Калининград', 'sales': 7, 'profit': 4 },
        { 'id': 21, 'name': 'СЦ Ереван', 'sales': 5, 'profit': 3 },
        { 'id': 22, 'name': 'Чашниково', 'sales': 3, 'profit': 2 },
        { 'id': 23, 'name': 'Обухово', 'sales': 1, 'profit': 1 },
        { 'id': 24, 'name': 'СЦ Барнаул', 'sales': 1, 'profit': 1 }
    ]

    sizeChart = [
        { 'size': '40', 'quantity': 2447, 'inTransit': 87 },
        { 'size': '42', 'quantity': 1939, 'inTransit': 261 },
        { 'size': '44', 'quantity': 1534, 'inTransit': 301 },
        { 'size': '46', 'quantity': 1380, 'inTransit': 203 },
        { 'size': '48', 'quantity': 1381, 'inTransit': 238 },
        { 'size': '50', 'quantity': 973, 'inTransit': 213 },
        { 'size': '52', 'quantity': 752, 'inTransit': 207 },
        { 'size': '54', 'quantity': 587, 'inTransit': 111 },
        { 'size': '56', 'quantity': 428, 'inTransit': 83 },
        { 'size': '58', 'quantity': 7, 'inTransit': 0 }
    ]

    selectedProducts = [
        {
            'id': 1,
            'name': 'Темно-синее пальто',
            'price': '12 999',
            'image': 'https://placehold.co/200x300/2c3e50/ffffff?text=Пальто',
            'sales': 150,
            'rating': 4.8
        },
        {
            'id': 2,
            'name': 'Черная зимняя куртка',
            'price': '15 999',
            'image': 'https://placehold.co/200x300/000000/ffffff?text=Куртка',
            'sales': 120,
            'rating': 4.5
        },
        {
            'id': 3,
            'name': 'Бежевое пуховое пальто',
            'price': '18 999',
            'image': 'https://placehold.co/200x300/d2b48c/ffffff?text=Пуховик',
            'sales': 95,
            'rating': 4.9
        },
        {
            'id': 4,
            'name': 'Зеленое зимнее пальто',
            'price': '14 999',
            'image': 'https://placehold.co/200x300/556b2f/ffffff?text=Пальто',
            'sales': 85,
            'rating': 4.3
        }
    ]

    return response_success(
        is_synced=False,
        stats=stats,
        chartData=chartData,
        baseStats=base_stats,
        abcAnalysis=abcAnalysis
    )