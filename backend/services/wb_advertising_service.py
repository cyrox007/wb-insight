"""
Сервис для работы со статистикой рекламных кампаний Wildberries

API Wildberries:
===============
- GET /api/advert/v2/adverts - список кампаний
  Документация: https://dev.wildberries.ru/docs/openapi/promotion/#tag/Kampanii/paths/~1api~1advert~1v2~1adverts/get
  
- GET /adv/v3/fullstats - полная статистика по кампаниям
  Документация: https://dev.wildberries.ru/docs/openapi/promotion/#tag/Statistika/paths/~1adv~1v3~1fullstats/get

Соответствие полей БД, API Wildberries и Excel:
=====================================================================================================
| Поле БД              | Поле API WB (camelCase)   | Колонка Excel       | Описание                  |
|----------------------|---------------------------|---------------------|---------------------------|
| campaign_id          | advertId                  | ID кампании         | ID рекламной кампании     |
| date                 | date                      | Дата                | Дата статистики           |
| platform_type        | platformType              | Тип Платформы       | Тип платформы (32, 64)    |
| product_name         | productName               | Имя товара          | Название товара           |
| nm_id                | nmId                      | nmId                | Артикул WB                |
| views                | views                     | Просмотры           | Количество просмотров     |
| clicks               | clicks                    | Клики               | Количество кликов         |
| ctr                  | ctr                       | CTR                 | CTR (%)                   |
| cpc                  | cpc                       | CPC                 | Цена за клик (₽)          |
| amount               | sum                       | Сумма               | Затраты на рекламу (₽)    |
| added_to_cart        | atbs                      | Добавлено в корзину | Добавления в корзину, шт. |
| orders               | orders                    | Заказы              | Количество заказов        |
| cr                   | cr                        | CR                  | Конверсия (%)             |
| shks                 | shks                      | SHKS                | Заказано товаров, шт.     |
| orders_amount        | sum_price                 | Сумма заказов       | Сумма заказов (₽)         |
| avg_position         | boosterStats[].avgPosition| avg_position        | Средняя позиция показа    |
| company              | companyName               | Компания            | Название компании         |
=====================================================================================================
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_advertising_stats import WbAdvertisingStats
from utils.batcher import chunks


def to_int(value: Any, default: int = 0) -> int:
    """Конвертирует значение в int"""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Конвертирует значение в Decimal"""
    if value is None:
        return default
    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return default


def to_str(value: Any) -> Optional[str]:
    """Конвертирует значение в строку"""
    if value is None:
        return None
    return str(value)


def parse_date_safe(value: Any) -> Optional[date]:
    """Безопасный парсинг даты"""
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            return None
    return None


def normalize_advertising_item(item: dict, user_id: UUID, token_id: UUID) -> dict:
    """
    Нормализует данные из API WB /adv/v3/fullstats в формат БД
    
    Соответствие полей API (camelCase) и БД (snake_case):
    =====================================================================================================
    | Поле БД              | Поле API WB (camelCase)        | Описание                        |
    |----------------------|--------------------------------|----------------------------------|
    | campaign_id          | advertId                       | ID кампании                     |
    | date                 | date                           | Дата статистики                 |
    | platform_type        | platformType                   | Тип платформы (32, 64)          |
    | product_name         | productName                    | Имя товара                      |
    | nm_id                | nmId                           | Артикул WB                      |
    | views                | views                          | Просмотры                       |
    | clicks               | clicks                         | Клики                           |
    | ctr                  | ctr                            | CTR (%)                         |
    | cpc                  | cpc                            | CPC (цена за клик)              |
    | amount               | sum                            | Затраты на рекламу (₽)          |
    | added_to_cart        | atbs                           | Добавлено в корзину             |
    | orders               | orders                         | Заказы                          |
    | cr                   | cr                             | CR (конверсия %)                |
    | shks                 | shks                           | Количество штук в заказах       |
    | orders_amount        | sum_price                      | Сумма заказов (₽)               |
    | avg_position         | boosterStats[].avgPosition     | Средняя позиция показа          |
    | company              | companyName                    | Компания                        |
    =====================================================================================================
    
    Args:
        item: Словарь с данными из API WB (структура ответа /adv/v3/fullstats)
        user_id: ID пользователя
        token_id: ID токена
        
    Returns:
        Словарь с нормализованными данными для БД
    """
    def pick(*keys: str) -> Any:
        """Берёт первое НЕ None значение из списка ключей"""
        for k in keys:
            if k in item and item[k] is not None:
                return item[k]
        return None

    # Извлекаем avg_position из boosterStats если есть
    avg_position = None
    booster_stats = item.get("boosterStats")
    if booster_stats and isinstance(booster_stats, list) and len(booster_stats) > 0:
        # boosterStats - это массив объектов, берем первый элемент
        avg_position = booster_stats[0].get("avgPosition")
    
    return {
        "user_id": user_id,
        "token_id": token_id,
        
        # Идентификаторы (advertId, nmId в API)
        "campaign_id": to_int(pick("advertId", "campaignId", "campaign_id")),
        "nm_id": to_int(pick("nmId", "nm_id")),
        
        # Дата
        "date": parse_date_safe(pick("date", "Date")),
        
        # Платформа и товар (platformType, productName, companyName в API)
        "platform_type": to_int(pick("platformType", "platform_type"), default=None),
        "product_name": to_str(pick("productName", "product_name", "Name")),
        "company": to_str(pick("companyName", "company", "Company")),
        
        # Метрики просмотров и кликов (views, clicks, ctr, cpc, sum в API)
        "views": to_int(pick("views", "Views")),
        "clicks": to_int(pick("clicks", "Clicks")),
        "ctr": to_decimal(pick("ctr", "CTR")),
        "cpc": to_decimal(pick("cpc", "CPC")),
        "amount": to_decimal(pick("sum", "amount", "Amount")),
        
        # Метрики конверсий (atbs, orders, cr, shks, sum_price в API)
        "added_to_cart": to_int(pick("atbs", "addedToCart", "added_to_cart", "ATC")),
        "orders": to_int(pick("orders", "Orders")),
        "cr": to_decimal(pick("cr", "CR")),
        "shks": to_int(pick("shks", "SHKS")),
        "orders_amount": to_decimal(pick("sum_price", "ordersAmount", "orders_amount", "ordersSum")),
        
        # Позиции (из boosterStats.avgPosition)
        "avg_position": to_decimal(avg_position, default=None),
        
        # Аудит
        "created_at": datetime.now(timezone.utc),
    }


async def save_advertising_stats(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict],
):
    """
    Сохраняет статистику по рекламным кампаниям в БД
    
    Args:
        session: сессия БД
        user_id: ID пользователя
        token_id: ID токена
        data: список словарей с данными из API
    """
    if not data:
        return

    BATCH_SIZE = 500
    for batch in chunks(data, BATCH_SIZE):
        normalized_batch = [normalize_advertising_item(item, user_id, token_id) for item in batch]
        
        stmt = insert(WbAdvertisingStats).values(normalized_batch)
        
        # Игнорируем дубликаты
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["user_id", "campaign_id", "nm_id", "date", "platform_type"]
        )
        
        await session.execute(stmt)


async def get_advertising_stats_by_campaign(
    session: AsyncSession,
    user_id: UUID,
    campaign_id: int,
    start_date: date,
    end_date: date
) -> List[WbAdvertisingStats]:
    """Получить статистику по конкретной кампании за период"""
    query = select(WbAdvertisingStats).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.campaign_id == campaign_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    ).order_by(WbAdvertisingStats.date)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_advertising_stats_by_nm_id(
    session: AsyncSession,
    user_id: UUID,
    nm_id: int,
    start_date: date,
    end_date: date
) -> List[WbAdvertisingStats]:
    """Получить статистику по артикулу за период"""
    query = select(WbAdvertisingStats).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.nm_id == nm_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    ).order_by(WbAdvertisingStats.date)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_aggregated_advertising_stats(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Получить агрегированную статистику по всем рекламным кампаниям за период
    
    Returns:
        Dict с суммарными метриками:
        - total_views: всего просмотров
        - total_clicks: всего кликов
        - total_amount: всего расходов
        - total_orders: всего заказов
        - total_orders_amount: сумма заказов
        - avg_ctr: средний CTR
        - avg_cpc: средний CPC
        - avg_cr: средний CR
    """
    query = select(
        func.sum(WbAdvertisingStats.views).label("total_views"),
        func.sum(WbAdvertisingStats.clicks).label("total_clicks"),
        func.sum(WbAdvertisingStats.amount).label("total_amount"),
        func.sum(WbAdvertisingStats.orders).label("total_orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("total_orders_amount"),
        func.avg(WbAdvertisingStats.ctr).label("avg_ctr"),
        func.avg(WbAdvertisingStats.cpc).label("avg_cpc"),
        func.avg(WbAdvertisingStats.cr).label("avg_cr"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    return {
        "total_views": int(row.total_views or 0),
        "total_clicks": int(row.total_clicks or 0),
        "total_amount": float(row.total_amount or 0),
        "total_orders": int(row.total_orders or 0),
        "total_orders_amount": float(row.total_orders_amount or 0),
        "avg_ctr": float(row.avg_ctr or 0),
        "avg_cpc": float(row.avg_cpc or 0),
        "avg_cr": float(row.avg_cr or 0),
    }


async def get_advertising_stats_by_day(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """Получить статистику по дням для графика"""
    query = select(
        WbAdvertisingStats.date.label("date"),
        func.sum(WbAdvertisingStats.views).label("views"),
        func.sum(WbAdvertisingStats.clicks).label("clicks"),
        func.sum(WbAdvertisingStats.amount).label("amount"),
        func.sum(WbAdvertisingStats.orders).label("orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("orders_amount"),
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
    
    return [
        {
            "date": row.date.isoformat(),
            "views": int(row.views or 0),
            "clicks": int(row.clicks or 0),
            "amount": float(row.amount or 0),
            "orders": int(row.orders or 0),
            "orders_amount": float(row.orders_amount or 0),
        }
        for row in rows
    ]


async def get_advertising_stats_by_campaign_and_day(
    session: AsyncSession,
    user_id: UUID,
    campaign_id: int,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """Получить статистику по кампании по дням"""
    query = select(
        WbAdvertisingStats.date.label("date"),
        func.sum(WbAdvertisingStats.views).label("views"),
        func.sum(WbAdvertisingStats.clicks).label("clicks"),
        func.sum(WbAdvertisingStats.amount).label("amount"),
        func.sum(WbAdvertisingStats.orders).label("orders"),
        func.sum(WbAdvertisingStats.orders_amount).label("orders_amount"),
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.campaign_id == campaign_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    ).group_by(
        WbAdvertisingStats.date
    ).order_by(
        WbAdvertisingStats.date
    )
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    return [
        {
            "date": row.date.isoformat(),
            "views": int(row.views or 0),
            "clicks": int(row.clicks or 0),
            "amount": float(row.amount or 0),
            "orders": int(row.orders or 0),
            "orders_amount": float(row.orders_amount or 0),
        }
        for row in rows
    ]


async def get_advertising_cost_by_nm_id(
    session: AsyncSession,
    user_id: UUID,
    nm_id: int,
    start_date: date,
    end_date: date
) -> float:
    """Получить сумму расходов на рекламу по артикулу за период"""
    query = select(
        func.sum(WbAdvertisingStats.amount).label("total_amount")
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.nm_id == nm_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    return float(row.total_amount or 0)


async def get_total_advertising_cost_for_user(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date
) -> float:
    """Получить общую сумму расходов на рекламу пользователя за период"""
    query = select(
        func.sum(WbAdvertisingStats.amount).label("total_amount")
    ).where(
        WbAdvertisingStats.user_id == user_id,
        WbAdvertisingStats.date >= start_date,
        WbAdvertisingStats.date <= end_date
    )
    
    result = await session.execute(query)
    row = result.one()
    
    return float(row.total_amount or 0)


# =============================================================================
# Методы для синхронизации с API Wildberries
# =============================================================================

async def sync_advertising_stats(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    wb_client,
    start_date: date,
    end_date: date
) -> int:
    """
    Синхронизирует статистику по рекламным кампаниям из API WB
    
    Процесс синхронизации:
    1. Получаем список всех рекламных кампаний (GET /api/advert/v2/adverts)
       - Передаем statuses для фильтрации (9=активна, 11=на паузе, 7=завершена, и т.д.)
    2. Извлекаем ID кампаний из поля "id" в ответе
    3. Разбиваем ID на батчи по 50 (ограничение API)
    4. Для каждого батча запрашиваем статистику (GET /adv/v3/fullstats)
       - Передаем ids, beginDate, endDate как query параметры
    5. Парсим ответ и сохраняем в БД
    
    Соответствие полей API и БД:
    ============================
    | Поле БД              | Поле API WB          | Описание                        |
    |----------------------|----------------------|----------------------------------|
    | campaign_id          | advertId             | ID кампании                     |
    | date                 | date (из days[])     | Дата статистики                 |
    | platform_type        | platformType         | Тип платформы (32, 64)          |
    | product_name         | productName          | Имя товара                      |
    | nm_id                | nmId                 | Артикул WB                      |
    | views                | views                | Просмотры                       |
    | clicks               | clicks               | Клики                           |
    | ctr                  | ctr                  | CTR (%)                         |
    | cpc                  | cpc                  | CPC (цена за клик)              |
    | amount               | sum                  | Затраты на рекламу (₽)          |
    | added_to_cart        | atbs                 | Добавлено в корзину             |
    | orders               | orders               | Заказы                          |
    | cr                   | cr                   | CR (конверсия %)                |
    | shks                 | shks                 | Количество штук в заказах       |
    | orders_amount        | sum_price            | Сумма заказов (₽)               |
    | avg_position         | boosterStats[].avgPosition | Средняя позиция показа   |
    | company              | companyName          | Компания                        |
    
    Args:
        session: сессия БД
        user_id: ID пользователя
        token_id: ID токена
        wb_client: экземпляр WBClient
        start_date: начало периода синхронизации
        end_date: конец периода синхронизации
        
    Returns:
        Количество сохраненных записей
    """
    from core.logger import setup_logger
    logger = setup_logger(__name__)
    
    # Шаг 1: Получаем список рекламных кампаний
    # Получаем активные (9), на паузе (11) и завершенные (7) кампании
    logger.info(f"Fetching advertising campaigns for user {user_id}")
    try:
        campaigns_response = await wb_client.get_advert_campaigns(params={"statuses": "9,11,7"})
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        raise RuntimeError(f"Ошибка получения списка кампаний: {e}")
    
    # campaigns_response имеет структуру: {"adverts": [...]}
    if isinstance(campaigns_response, dict) and "adverts" in campaigns_response:
        campaigns = campaigns_response["adverts"]
    elif isinstance(campaigns_response, list):
        campaigns = campaigns_response
    else:
        campaigns = []
    
    if not campaigns:
        logger.info("No advertising campaigns found")
        return 0
    
    # Шаг 2: Извлекаем ID кампаний (поле "id" в API v2)
    campaign_ids = []
    for campaign in campaigns:
        campaign_id = campaign.get("id")
        if campaign_id:
            campaign_ids.append(str(campaign_id))
    
    if not campaign_ids:
        logger.info("No campaign IDs found")
        return 0
    
    logger.info(f"Found {len(campaign_ids)} campaigns to fetch stats for")
    
    # Шаг 3: Разбиваем на батчи по 50 (ограничение API)
    BATCH_SIZE = 50
    all_normalized_data = []
    
    for i in range(0, len(campaign_ids), BATCH_SIZE):
        batch_ids = campaign_ids[i:i + BATCH_SIZE]
        ids_str = ",".join(batch_ids)
        
        # Шаг 4: Запрашиваем статистику по батчу
        # API v3 fullstats требует GET запрос с query параметрами
        stats_params = {
            "ids": ids_str,
            "beginDate": start_date.isoformat(),
            "endDate": end_date.isoformat()
        }
        
        logger.info(f"Fetching stats for batch {i//BATCH_SIZE + 1}: {len(batch_ids)} campaigns from {start_date} to {end_date}")
        try:
            stats_response = await wb_client.get_advert_stats(params=stats_params)
        except Exception as e:
            logger.error(f"Error fetching stats for batch: {e}")
            continue
        
        # stats_response - это массив объектов статистики
        if isinstance(stats_response, list):
            batch_stats = stats_response
        elif isinstance(stats_response, dict) and "data" in stats_response:
            batch_stats = stats_response["data"]
        else:
            batch_stats = []
        
        if not batch_stats:
            logger.info("No stats data returned from API for this batch")
            continue
        
        # Шаг 5: Обрабатываем ответ API
        # API возвращает структуру: [{advertId: 123, views: ..., clicks: ..., days: [...], boosterStats: [...]}, ...]
        for campaign_stat in batch_stats:
            advert_id = campaign_stat.get("advertId")
            if not advert_id:
                continue
            
            # Данные за каждый день находятся в массиве days[]
            days_stats = campaign_stat.get("days", [])
            
            # boosterStats - общий для всей кампании или может быть по дням
            booster_stats = campaign_stat.get("boosterStats", [])
            avg_position = None
            if booster_stats and isinstance(booster_stats, list) and len(booster_stats) > 0:
                avg_position = booster_stats[0].get("avgPosition")
            
            for day_stat in days_stats:
                date_str = day_stat.get("date")
                if not date_str:
                    continue
                
                # Формируем запись для БД
                record = {
                    "advertId": advert_id,
                    "date": date_str,
                    # Основные метрики из day_stat
                    "views": day_stat.get("views", 0),
                    "clicks": day_stat.get("clicks", 0),
                    "ctr": day_stat.get("ctr", 0),
                    "cpc": day_stat.get("cpc", 0),
                    "sum": day_stat.get("sum", 0),
                    "atbs": day_stat.get("atbs", 0),
                    "orders": day_stat.get("orders", 0),
                    "cr": day_stat.get("cr", 0),
                    "shks": day_stat.get("shks", 0),
                    "sum_price": day_stat.get("sum_price", 0),
                    # Дополнительные поля
                    "platformType": day_stat.get("platformType"),
                    "productName": day_stat.get("productName"),
                    "nmId": day_stat.get("nmId"),
                    "companyName": day_stat.get("companyName"),
                    "avgPosition": avg_position,
                }
                
                all_normalized_data.append(record)
    
    if not all_normalized_data:
        logger.info("No data to save after normalization")
        return 0
    
    # Шаг 6: Сохраняем в БД
    logger.info(f"Saving {len(all_normalized_data)} records to database")
    await save_advertising_stats(session, user_id, token_id, all_normalized_data)
    
    return len(all_normalized_data)


async def get_or_sync_advertising_cost_by_nm_id(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    wb_client,
    nm_id: int,
    start_date: date,
    end_date: date,
    force_sync: bool = False
) -> float:
    """
    Получает расходы на рекламу по артикулу из БД, при необходимости синхронизируя с API
    
    Args:
        session: сессия БД
        user_id: ID пользователя
        token_id: ID токена
        wb_client: экземпляр WBClient
        nm_id: артикул товара
        start_date: начало периода
        end_date: конец периода
        force_sync: принудительная синхронизация даже если есть данные
        
    Returns:
        Сумма расходов на рекламу
    """
    from core.logger import setup_logger
    logger = setup_logger(__name__)
    
    # Проверяем наличие данных в БД
    existing_cost = await get_advertising_cost_by_nm_id(
        session, user_id, nm_id, start_date, end_date
    )
    
    # Если есть данные и не требуется принудительная синхронизация - возвращаем
    if existing_cost > 0 and not force_sync:
        logger.debug(f"Using cached advertising cost {existing_cost} for nm_id {nm_id}")
        return existing_cost
    
    # Синхронизируем данные
    logger.info(f"Syncing advertising stats for nm_id {nm_id}")
    count = await sync_advertising_stats(
        session, user_id, token_id, wb_client, start_date, end_date
    )
    logger.info(f"Synced {count} records")
    
    # Получаем обновленные данные
    updated_cost = await get_advertising_cost_by_nm_id(
        session, user_id, nm_id, start_date, end_date
    )
    
    return updated_cost


async def get_or_sync_total_advertising_cost(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    wb_client,
    start_date: date,
    end_date: date,
    force_sync: bool = False
) -> float:
    """
    Получает общие расходы на рекламу пользователя из БД, при необходимости синхронизируя с API
    
    Args:
        session: сессия БД
        user_id: ID пользователя
        token_id: ID токена
        wb_client: экземпляр WBClient
        start_date: начало периода
        end_date: конец периода
        force_sync: принудительная синхронизация даже если есть данные
        
    Returns:
        Общая сумма расходов на рекламу
    """
    from core.logger import setup_logger
    logger = setup_logger(__name__)
    
    # Проверяем наличие данных в БД
    existing_cost = await get_total_advertising_cost_for_user(
        session, user_id, start_date, end_date
    )
    
    # Если есть данные и не требуется принудительная синхронизация - возвращаем
    if existing_cost > 0 and not force_sync:
        logger.debug(f"Using cached total advertising cost {existing_cost}")
        return existing_cost
    
    # Синхронизируем данные
    logger.info("Syncing total advertising stats")
    count = await sync_advertising_stats(
        session, user_id, token_id, wb_client, start_date, end_date
    )
    logger.info(f"Synced {count} records")
    
    # Получаем обновленные данные
    updated_cost = await get_total_advertising_cost_for_user(
        session, user_id, start_date, end_date
    )
    
    return updated_cost
