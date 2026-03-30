import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from uuid import UUID as UUIDType

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.wb_products import WbProduct, WbProductStock, ProductSyncLog
from schemas.products import (
    WbCardSchema,
    WbPriceSchema,
    WbSizeSchema,
    WbPhotoUrlsSchema,
    WbVideoSchema,
    WbWholesaleSchema,
    WbDimensionsSchema,
    WbCharacteristicSchema,
    WbTagSchema,
    TagColorEnum,
    WbCardsListResponseSchema,
    ModerationStatusEnum
)


# Эмуляция данных для складов
WAREHOUSES = [
    ("Тула", 1),
    ("Электросталь", 2),
    ("Коледино", 3),
    ("Краснодар", 4),
    ("Казань", 5),
    ("Рязань (Тюшевское)", 6),
    ("Невинномысск", 7),
    ("Екатеринбург - Испытателей 14г", 8),
    ("Самара (Новосемейкино)", 9),
    ("Санкт-Петербург Уткина Заводь", 10),
    ("Новосибирск", 11),
    ("Котовск", 12),
    ("Владимир", 13),
    ("Волгоград", 14),
    ("Воронеж", 15),
    ("Сарапул", 16),
    ("Екатеринбург - Перспективный 12", 17),
    ("Астана Карагандинское шоссе", 18),
    ("Белая дача", 19),
    ("Актобе", 20),
    ("Атакент", 21),
    ("Калининград", 22),
    ("СЦ Ереван", 23),
    ("Чашниково", 24),
    ("Обухово", 25),
    ("СЦ Барнаул", 26),
]

# Эмуляция размеров
SIZES = ["40", "42", "44", "46", "48", "50", "52", "54", "56", "58"]

# Эмуляция категорий
CATEGORIES = [
    "Одежда",
    "Обувь",
    "Аксессуары",
    "Дом и сад",
    "Красота",
    "Детские товары",
    "Спорт",
    "Электроника"
]

# Эмуляция брендов
BRANDS = [
    "Модный Бренд",
    "Стиль",
    "Премиум",
    "Эконом",
    "Люкс",
    "Базовый",
    "Трендовый",
    "Классика"
]

# Названия товаров
PRODUCT_NAMES = [
    "Платье женское вечернее",
    "Рубашка мужская классическая",
    "Блузка атласная",
    "Пальто зимнее",
    "Куртка демисезонная",
    "Юбка карандаш",
    "Брюки классические",
    "Футболка базовая",
    "Свитер шерстяной",
    "Кардиган вязаный",
    "Джинсы прямые",
    "Костюм деловой",
    "Топ летний",
    "Сарафан пляжный",
    "Жакет приталенный"
]

# Цвета
COLORS = [
    ("Красный", "red"),
    ("Синий", "blue"),
    ("Черный", "black"),
    ("Белый", "white"),
    ("Бежевый", "beige"),
    ("Зеленый", "green"),
    ("Серый", "gray"),
    ("Коричневый", "brown")
]


def generate_wb_card(
    nm_id: int,
    vendor_code: str,
    title: str,
    brand: str,
    subject_name: str,
    user_id: UUIDType
) -> WbCardSchema:
    """
    Генерация карточки товара в формате WB API.
    
    Полностью соответствует структуре ответа /content/v2/get/cards/list
    """
    now = datetime.now(timezone.utc)
    days_ago = random.randint(1, 365)
    created_at = now - timedelta(days=days_ago)
    updated_at = created_at + timedelta(days=random.randint(1, min(30, days_ago)))
    
    # Генерируем цены в копейках (как в WB API)
    retail_price_kopecks = random.randint(200000, 2000000)  # 2000 - 20000 руб
    discount_percent = random.randint(5, 50)
    discounted_price_kopecks = int(retail_price_kopecks * (100 - discount_percent) / 100)
    
    prices = WbPriceSchema(
        price=retail_price_kopecks,
        discountedPrice=discounted_price_kopecks,
        clubPrice=int(discounted_price_kopecks * 0.95) if random.random() > 0.7 else None
    )
    
    # Генерируем варианты (размеры)
    sizes_count = random.randint(1, 5)
    selected_sizes = random.sample(SIZES, sizes_count)
    
    sizes = []
    for idx, size in enumerate(selected_sizes):
        barcode = f"46{random.randint(1000000000, 9999999999)}"
        
        sizes.append(WbSizeSchema(
            chrtID=random.randint(1000000, 9999999),
            techSize=size,
            wbSize=size,
            skus=[barcode]
        ))
    
    # Генерируем фотографии с разными форматами URL
    photos_count = random.randint(3, 10)
    photos = []
    base_url = f"https://basket-{random.randint(1, 15)}.wb.ru/vol{random.randint(1, 1000)}/part{random.randint(1, 100)}/{nm_id}"
    
    # Видео URL (опционально, добавляем в первое фото)
    video_url = None
    if random.random() > 0.7:
        video_url = f"{base_url}/video/video_{random.randint(1, 100)}.mp4"
    
    for i in range(photos_count):
        photo_video = video_url if i == 0 and video_url else None
        photos.append(WbPhotoUrlsSchema(
            big=f"{base_url}/images/big/{i}.jpg",
            c246x328=f"{base_url}/images/c246x328/{i}.jpg",
            c516x688=f"{base_url}/images/c516x688/{i}.jpg",
            square=f"{base_url}/images/square/{i}.jpg",
            tm=f"{base_url}/images/tm/{i}.jpg",
            video=photo_video
        ))
    
    # Видео как отдельный список (устаревший формат, для совместимости)
    video = None
    if video_url:
        video = [WbVideoSchema(
            url=video_url,
            name=f"Видео {nm_id}"
        )]
    
    # Оптовая продажа (опционально)
    wholesale = None
    if random.random() > 0.8:
        wholesale = WbWholesaleSchema(
            enabled=True,
            quantum=random.randint(2, 10)
        )
    
    # Габариты и вес
    length = round(random.uniform(20, 60), 1)
    width = round(random.uniform(15, 40), 1)
    height = round(random.uniform(5, 20), 1)
    weight = round(random.uniform(0.1, 3.0), 3)
    
    dimensions = WbDimensionsSchema(
        length=length,
        width=width,
        height=height,
        weightBrutto=weight,
        isValid=True
    )
    
    # Генерируем характеристики
    characteristics = [
        WbCharacteristicSchema(
            id=random.randint(1, 1000),
            name="Состав",
            value=f"{random.randint(70, 100)}% хлопок"
        ),
        WbCharacteristicSchema(
            id=random.randint(1, 1000),
            name="Вес товара, г",
            value=random.randint(100, 2000)
        ),
        WbCharacteristicSchema(
            id=random.randint(1, 1000),
            name="Страна производства",
            value="Россия"
        ),
        WbCharacteristicSchema(
            id=random.randint(1, 1000),
            name="Тип застежки",
            value=random.choice(["Пуговицы", "Молния", "Нет"])
        ),
    ]
    
    # Ярлыки (опционально)
    tags = []
    if random.random() > 0.5:
        tag_colors = list(TagColorEnum)
        tags_count = random.randint(1, 3)
        for i in range(tags_count):
            tags.append(WbTagSchema(
                id=random.randint(1, 100),
                name=f"Ярлык {i+1}",
                color=random.choice(tag_colors)
            ))
    
    return WbCardSchema(
        nmID=nm_id,
        imtID=nm_id // 10,  # Группируем по 10 товаров
        nmUUID=f"00000000-0000-0000-0000-{nm_id:012d}",
        subjectID=random.randint(1, 100),
        subjectName=subject_name,
        vendorCode=vendor_code,
        brand=brand,
        title=title,
        description=f"Описание товара {nm_id}. Отличное качество, современный дизайн. {title} от бренда {brand}.",
        needKiz=random.random() < 0.3,  # 30% требуют маркировку
        photos=photos,
        video=video,
        wholesale=wholesale,
        dimensions=dimensions,
        characteristics=characteristics,
        sizes=sizes,
        tags=tags,
        createdAt=created_at,
        updatedAt=updated_at
    )


async def emulate_wb_cards_sync(
    session: AsyncSession,
    user_id: UUIDType,
    products_count: int = 50,
    sync_type: str = "full"
) -> WbCardsListResponseSchema:
    """
    Эмуляция получения карточек товаров из WB API.
    
    Возвращает данные в формате, идентичном реальному API Wildberries.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        products_count: Количество товаров
        sync_type: Тип синхронизации
        
    Returns:
        WbCardsListResponseSchema со списком карточек
    """
    cards = []
    
    # Предметы/категории для эмуляции
    subjects = [
        "Платья",
        "Рубашки",
        "Блузки",
        "Пальто",
        "Куртки",
        "Юбки",
        "Брюки",
        "Футболки",
        "Свитера",
        "Кардиганы",
        "Джинсы",
        "Костюмы",
        "Топы",
        "Сарафаны",
        "Жакеты"
    ]
    
    for i in range(products_count):
        nm_id = 10000000 + i
        vendor_code = f"ART-{random.randint(1000, 9999)}"
        subject_name = random.choice(subjects)
        title = f"{subject_name} {random.choice(['красный', 'синий', 'черный', 'белый', 'бежевый'])}"
        brand = random.choice(BRANDS)
        
        card = generate_wb_card(
            nm_id=nm_id,
            vendor_code=vendor_code,
            title=title,
            brand=brand,
            subject_name=subject_name,
            user_id=user_id
        )
        cards.append(card)
    
    return WbCardsListResponseSchema(
        cards=cards,
        total=products_count,
        limit=products_count,
        offset=0
    )


async def emulate_product_sync(
    session: AsyncSession,
    user_id: UUIDType,
    products_count: int = 50,
    sync_type: str = "full"
) -> ProductSyncLog:
    """
    Эмуляция синхронизации товаров пользователя.
    
    Создаёт тестовые данные о товарах и остатках на складах.
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        products_count: Количество товаров для создания
        sync_type: Тип синхронизации
        
    Returns:
        Объект лога синхронизации
    """
    # Создаём лог синхронизации
    sync_log = ProductSyncLog(
        user_id=user_id,
        sync_type=sync_type,
        status="in_progress",
        source="emulation"
    )
    session.add(sync_log)
    await session.flush()
    
    try:
        # Проверяем существующие товары
        existing_query = select(WbProduct.nm_id).where(
            WbProduct.user_id == user_id
        )
        result = await session.execute(existing_query)
        existing_nm_ids = set(row[0] for row in result.fetchall())
        
        products_created = 0
        products_updated = 0
        stocks_processed = 0
        
        for i in range(products_count):
            # Генерируем nm_id
            nm_id = 10000000 + i
            
            # Проверяем существует ли товар
            product_query = select(WbProduct).where(
                WbProduct.user_id == user_id,
                WbProduct.nm_id == nm_id
            )
            result = await session.execute(product_query)
            product = result.scalar_one_or_none()
            
            if product is None:
                # Создаём новый товар
                product = WbProduct(
                    user_id=user_id,
                    nm_id=nm_id,
                    vendor_code=f"ART-{random.randint(1000, 9999)}",
                    barcode=f"46{random.randint(1000000000, 9999999999)}",
                    name=f"{random.choice(PRODUCT_NAMES)} {random.choice(['красный', 'синий', 'черный', 'белый', 'бежевый'])}",
                    brand=random.choice(BRANDS),
                    category=random.choice(CATEGORIES),
                    subcategory=f"Подкатегория {random.randint(1, 10)}",
                    description=f"Описание товара {nm_id}. Отличное качество, современный дизайн.",
                    retail_price=round(random.uniform(2000, 20000), 2),
                    sale_price=round(random.uniform(1500, 15000), 2),
                    discount_percent=round(random.uniform(5, 50), 1),
                    purchase_price=round(random.uniform(500, 8000), 2),
                    vat_percent=20.0,
                    size=random.choice(SIZES),
                    color=random.choice(["Красный", "Синий", "Черный", "Белый", "Бежевый"]),
                    weight=random.randint(100, 2000),
                    dimensions=f"{random.randint(20, 50)}x{random.randint(15, 40)}x{random.randint(5, 15)}",
                    volume=round(random.uniform(0.5, 5.0), 2),
                    is_active=random.random() > 0.1,  # 90% активные
                    is_archived=random.random() < 0.05,  # 5% архивные
                    moderation_status="approved",
                    main_image_url=f"https://example.com/images/{nm_id}.jpg",
                    images_count=random.randint(3, 10),
                    rating=round(random.uniform(3.5, 5.0), 1),
                    reviews_count=random.randint(0, 500),
                    questions_count=random.randint(0, 50),
                    total_orders=random.randint(10, 1000),
                    total_sales=random.randint(5, 800),
                    total_revenue=round(random.uniform(50000, 5000000), 2),
                    first_sale_date=datetime.now(timezone.utc).date() - timedelta(days=random.randint(1, 365)),
                    last_sale_date=datetime.now(timezone.utc).date() - timedelta(days=random.randint(0, 30))
                )
                session.add(product)
                products_created += 1
            else:
                # Обновляем существующий товар
                product.sale_price = round(random.uniform(1500, 15000), 2)
                product.total_sales = random.randint(5, 800)
                product.updated_at = datetime.now(timezone.utc)
                products_updated += 1
            
            await session.flush()
            
            # Создаём остатки по складам (для каждого товара 3-7 складов)
            warehouses_count = random.randint(3, 7)
            selected_warehouses = random.sample(WAREHOUSES, warehouses_count)
            
            for warehouse_name, warehouse_id in selected_warehouses:
                quantity = random.randint(0, 500)
                in_transit = random.randint(0, 100)
                reserved = random.randint(0, min(50, quantity))
                
                stock_query = select(WbProductStock).where(
                    WbProductStock.product_id == product.id,
                    WbProductStock.warehouse_name == warehouse_name
                )
                result = await session.execute(stock_query)
                stock = result.scalar_one_or_none()
                
                if stock is None:
                    stock = WbProductStock(
                        product_id=product.id,
                        user_id=user_id,
                        nm_id=nm_id,
                        barcode=product.barcode,
                        warehouse_name=warehouse_name,
                        warehouse_id=warehouse_id,
                        region=f"Регион {random.randint(1, 8)}",
                        quantity=quantity,
                        quantity_in_transit=in_transit,
                        quantity_reserved=reserved,
                        quantity_available=max(0, quantity - reserved)
                    )
                    session.add(stock)
                else:
                    stock.quantity = quantity
                    stock.quantity_in_transit = in_transit
                    stock.quantity_reserved = reserved
                    stock.quantity_available = max(0, quantity - reserved)
                    stock.updated_at = datetime.now(timezone.utc)
                
                stocks_processed += 1
        
        # Обновляем лог синхронизации
        sync_log.status = "success"
        sync_log.products_loaded = products_count
        sync_log.products_created = products_created
        sync_log.products_updated = products_updated
        sync_log.products_deleted = 0
        sync_log.stocks_processed = stocks_processed
        sync_log.errors_count = 0
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.duration_seconds = (sync_log.finished_at - sync_log.started_at).total_seconds()
        
        await session.commit()
        
        return sync_log
        
    except Exception as e:
        # Ошибка при синхронизации
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.duration_seconds = (sync_log.finished_at - sync_log.started_at).total_seconds()
        
        await session.rollback()
        raise


async def get_last_sync_log(
    session: AsyncSession,
    user_id: UUIDType
) -> ProductSyncLog | None:
    """
    Получение последнего лога синхронизации пользователя.
    
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


async def clear_user_products(
    session: AsyncSession,
    user_id: UUIDType
) -> dict:
    """
    Удаление всех товаров пользователя (для тестирования).
    
    Args:
        session: Асинхронная сессия БД
        user_id: ID пользователя
        
    Returns:
        Статистика удалённых данных
    """
    from sqlalchemy import delete
    
    # Удаляем остатки
    stocks_query = delete(WbProductStock).where(
        WbProductStock.user_id == user_id
    )
    result = await session.execute(stocks_query)
    stocks_deleted = result.rowcount
    
    # Удаляем товары
    products_query = delete(WbProduct).where(
        WbProduct.user_id == user_id
    )
    result = await session.execute(products_query)
    products_deleted = result.rowcount
    
    await session.commit()
    
    return {
        "products_deleted": products_deleted,
        "stocks_deleted": stocks_deleted
    }
