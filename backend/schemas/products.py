from datetime import date, datetime
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


# ========== ENUM для статусов и цветов ==========

class ModerationStatusEnum(str, Enum):
    """Статусы модерации карточки товара"""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    MODERATION = "moderation"
    PRE_MODERATION = "pre_moderation"


class TagColorEnum(str, Enum):
    """Цвета ярлыков"""
    GRAY = "D1CFD7"
    RED = "FEE0E0"
    PURPLE = "ECDAFF"
    BLUE = "E4EAFF"
    GREEN = "DEF1DD"
    YELLOW = "FFECC7"


# ========== Схемы для WB API /content/v2/get/cards/list ==========

class WbPhotoUrlsSchema(BaseModel):
    """Схема URL фотографий из WB API"""
    big: str = Field(..., description="URL фото 900x1200")
    c246x328: str = Field(..., description="URL фото 248x328")
    c516x688: str = Field(..., description="URL фото 516x688")
    square: str = Field(..., description="URL фото 600x600")
    tm: str = Field(..., description="URL фото 75x100")
    video: Optional[str] = Field(None, description="URL видео")
    
    class Config:
        from_attributes = True


class WbVideoSchema(BaseModel):
    """Схема видео из WB API (устаревшая, video теперь в photos)"""
    url: str = Field(..., description="URL видео")
    name: Optional[str] = Field(None, description="Название видео")
    
    class Config:
        from_attributes = True


class WbWholesaleSchema(BaseModel):
    """Схема оптовой продажи"""
    enabled: bool = Field(False, description="Предназначена ли карточка для оптовой продажи")
    quantum: Optional[int] = Field(None, ge=1, description="Количество единиц товара в упаковке")
    
    class Config:
        from_attributes = True


class WbDimensionsSchema(BaseModel):
    """Схема габаритов и веса товара"""
    length: Optional[float] = Field(None, description="Длина, см")
    width: Optional[float] = Field(None, description="Ширина, см")
    height: Optional[float] = Field(None, description="Высота, см")
    weightBrutto: Optional[float] = Field(None, description="Вес брутто, кг", le=999.999)
    isValid: bool = Field(True, description="Потенциальная некорректность габаритов")
    
    class Config:
        from_attributes = True


class WbCharacteristicSchema(BaseModel):
    """Схема характеристики товара из WB API"""
    id: int = Field(..., description="ID характеристики")
    name: str = Field(..., description="Название характеристики")
    value: Union[str, int, float, bool, None] = Field(..., description="Значение характеристики")
    
    class Config:
        from_attributes = True


class WbSizeSchema(BaseModel):
    """Схема размера/варианта товара из WB API"""
    chrtID: int = Field(..., description="Числовой ID размера для данного артикула WB")
    techSize: str = Field(..., description="Размер товара (А, XXL, 57 и др.)")
    wbSize: str = Field(..., description="Российский размер товара")
    skus: List[str] = Field(default_factory=list, description="Баркод товара (список)")
    
    class Config:
        from_attributes = True


class WbTagSchema(BaseModel):
    """Схема ярлыка"""
    id: int = Field(..., description="ID ярлыка")
    name: str = Field(..., description="Название ярлыка")
    color: TagColorEnum = Field(..., description="Цвет ярлыка")
    
    class Config:
        from_attributes = True


class WbPriceSchema(BaseModel):
    """Схема цены из WB API (в копейках)"""
    price: int = Field(..., description="Розничная цена в копейках")
    discountedPrice: int = Field(..., description="Цена со скидкой в копейках")
    clubPrice: Optional[int] = Field(None, description="Клубная цена в копейках")
    
    @property
    def price_rub(self) -> float:
        """Цена в рублях"""
        return self.price / 100
    
    @property
    def discounted_price_rub(self) -> float:
        """Цена со скидкой в рублях"""
        return self.discountedPrice / 100
    
    @property
    def club_price_rub(self) -> Optional[float]:
        """Клубная цена в рублях"""
        return self.clubPrice / 100 if self.clubPrice else None
    
    class Config:
        from_attributes = True


class WbCardSchema(BaseModel):
    """
    Схема карточки товара из WB API /content/v2/get/cards/list
    
    Полностью соответствует структуре ответа Wildberries Content API v2
    """
    # Основные идентификаторы
    nmID: int = Field(..., description="Артикул WB")
    imtID: int = Field(..., description="ID для объединённых карточек товаров")
    nmUUID: str = Field(..., description="Внутренний технический ID карточки товара (UUID)")
    
    # Категория и предмет
    subjectID: int = Field(..., description="ID предмета")
    subjectName: str = Field(..., description="Название предмета")
    
    # Основная информация
    vendorCode: str = Field(..., description="Артикул продавца")
    brand: str = Field(..., description="Бренд")
    title: str = Field(..., description="Наименование товара")
    description: Optional[str] = Field(None, description="Описание товара")
    
    # Маркировка
    needKiz: bool = Field(False, description="Требуется ли код маркировки")
    
    # Фотографии (video теперь внутри каждого элемента photos)
    photos: List[WbPhotoUrlsSchema] = Field(default_factory=list, description="Массив фото")
    video: Optional[List[WbVideoSchema]] = Field(None, description="Видео (устаревшее поле)")
    
    # Оптовая продажа
    wholesale: Optional[WbWholesaleSchema] = Field(None, description="Оптовая продажа")
    
    # Габариты и вес
    dimensions: Optional[WbDimensionsSchema] = Field(None, description="Габариты и вес товара")
    
    # Характеристики
    characteristics: List[WbCharacteristicSchema] = Field(default_factory=list, description="Характеристики")
    
    # Размеры
    sizes: List[WbSizeSchema] = Field(default_factory=list, description="Размеры товара")
    
    # Ярлыки
    tags: List[WbTagSchema] = Field(default_factory=list, description="Ярлыки")
    
    # Даты
    createdAt: datetime = Field(..., description="Дата и время создания")
    updatedAt: datetime = Field(..., description="Дата и время изменения")
    
    class Config:
        populate_by_name = True
        from_attributes = True


class WbCardsListResponseSchema(BaseModel):
    """
    Схема ответа WB API /content/v2/get/cards/list
    
    Полный формат ответа с пагинацией
    """
    cards: List[WbCardSchema] = Field(default_factory=list, description="Список карточек товаров")
    total: int = Field(0, description="Общее количество товаров")
    limit: int = Field(100, description="Лимит записей")
    offset: int = Field(0, description="Смещение")
    
    class Config:
        from_attributes = True


# ========== Схемы для запросов к WB API ==========

class WbCardsFilterSchema(BaseModel):
    """Схема фильтра для запроса списка карточек"""
    withPhoto: int = Field(-1, description="-1 все, 0 без фото, 1 с фото")
    size: List[str] = Field(default_factory=list, description="Фильтр по размерам")
    colors: List[str] = Field(default_factory=list, description="Фильтр по цветам")
    status: List[str] = Field(default_factory=list, description="Статус модерации")
    subjectIDs: List[int] = Field(default_factory=list, description="ID предметов")
    categories: List[str] = Field(default_factory=list, description="Категории")
    brands: List[str] = Field(default_factory=list, description="Бренды")
    
    class Config:
        from_attributes = True


class WbCardsCursorSchema(BaseModel):
    """Схема курсора для пагинации"""
    limit: int = Field(100, ge=1, le=1000, description="Количество записей")
    offset: int = Field(0, ge=0, description="Смещение")
    
    class Config:
        from_attributes = True


class WbGetCardsRequestSchema(BaseModel):
    """Схема запроса к /content/v2/get/cards/list"""
    filter: WbCardsFilterSchema = Field(default_factory=WbCardsFilterSchema)
    cursor: WbCardsCursorSchema = Field(default_factory=WbCardsCursorSchema)
    
    class Config:
        from_attributes = True


# ========== Схемы для остатков ==========

# WB API Stock Schema
class WbStocksItemSchema(BaseModel):
    """Схема остатка товара на складе из WB API"""
    warehouseID: int = Field(..., description="ID склада")
    warehouseName: str = Field(..., description="Название склада")
    quantity: int = Field(0, description="Количество на складе")
    inWay: int = Field(0, description="В пути")
    reservation: int = Field(0, description="Зарезервировано")
    
    class Config:
        from_attributes = True


class WbStocksResponseSchema(BaseModel):
    """Схема ответа WB API по остаткам"""
    stocks: List[WbStocksItemSchema] = Field(default_factory=list)
    
    class Config:
        from_attributes = True



class ProductStockSchema(BaseModel):
    """Схема остатка товара на складе"""
    id: UUID
    warehouse_name: str = Field(..., description="Название склада")
    warehouse_id: Optional[int] = Field(None, description="ID склада")
    region: Optional[str] = Field(None, description="Регион склада")
    quantity: int = Field(0, description="Количество на складе")
    quantity_in_transit: int = Field(0, description="Количество в пути")
    quantity_reserved: int = Field(0, description="Зарезервировано")
    quantity_available: int = Field(0, description="Доступно")
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== Схемы для товаров ==========

class ProductBaseSchema(BaseModel):
    """Базовая схема товара"""
    nm_id: int = Field(..., description="Артикул WB (nmID)")
    vendor_code: Optional[str] = Field(None, description="Артикул продавца")
    barcode: Optional[str] = Field(None, description="Штрихкод")
    name: str = Field(..., description="Название товара")
    brand: Optional[str] = Field(None, description="Бренд")
    category: Optional[str] = Field(None, description="Категория")
    subcategory: Optional[str] = Field(None, description="Подкатегория")
    description: Optional[str] = Field(None, description="Описание")
    
    # Цены
    retail_price: Optional[float] = Field(None, description="Розничная цена")
    sale_price: Optional[float] = Field(None, description="Цена продажи")
    discount_percent: Optional[float] = Field(None, description="Скидка %")
    purchase_price: Optional[float] = Field(None, description="Закупочная цена")
    vat_percent: Optional[float] = Field(None, description="НДС %")
    
    # Характеристики
    size: Optional[str] = Field(None, description="Размер")
    color: Optional[str] = Field(None, description="Цвет")
    weight: Optional[int] = Field(None, description="Вес (г)")
    dimensions: Optional[str] = Field(None, description="Габариты")
    volume: Optional[float] = Field(None, description="Объем (л)")
    
    # Статусы
    is_active: bool = Field(True, description="Активен")
    is_archived: bool = Field(False, description="Архивирован")
    moderation_status: Optional[str] = Field(None, description="Статус модерации")
    
    # Фото
    main_image_url: Optional[str] = Field(None, description="URL главного фото")
    images_count: int = Field(0, description="Количество фото")
    
    # Рейтинги
    rating: Optional[float] = Field(None, description="Рейтинг")
    reviews_count: int = Field(0, description="Количество отзывов")
    questions_count: int = Field(0, description="Количество вопросов")
    
    # Продажи (агрегированные)
    total_orders: int = Field(0, description="Всего заказов")
    total_sales: int = Field(0, description="Всего продаж")
    total_revenue: Optional[float] = Field(None, description="Выручка всего")
    
    # Даты
    created_at: datetime
    updated_at: datetime
    first_sale_date: Optional[date] = None
    last_sale_date: Optional[date] = None
    
    class Config:
        from_attributes = True


class ProductSchema(ProductBaseSchema):
    """Полная схема товара с ID"""
    id: UUID
    user_id: UUID
    
    class Config:
        from_attributes = True


class ProductListItemSchema(BaseModel):
    """Схема товара для списка"""
    id: UUID
    nm_id: int
    vendor_code: Optional[str]
    name: str
    brand: Optional[str]
    category: Optional[str]
    sale_price: Optional[float]
    retail_price: Optional[float]
    discount_percent: Optional[float]
    rating: Optional[float]
    reviews_count: int
    main_image_url: Optional[str]
    total_sales: int
    total_orders: int
    total_revenue: Optional[float]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductWithStocksSchema(ProductBaseSchema):
    """Схема товара с остатками"""
    id: UUID
    user_id: UUID
    stocks: List[ProductStockSchema] = Field(default_factory=list, description="Остатки по складам")
    
    class Config:
        from_attributes = True


# ========== Схемы для статистики и аналитики ==========

class WarehouseStatSchema(BaseModel):
    """Статистика по складу"""
    name: str
    sum: int = Field(..., description="Общее количество (для совместимости)")
    stock: int = Field(0, description="На складе")
    in_transit: int = Field(0, description="В пути")
    reserved: int = Field(0, description="Зарезервировано")
    available: int = Field(0, description="Доступно")
    goodsAmount: float = Field(0, description="Стоимость товара")


class SizeDistributionSchema(BaseModel):
    """Распределение по размерам"""
    size: str
    quantity: int = Field(0, description="Количество")
    inTransit: int = Field(0, description="В пути")


class AbcAnalysisItemSchema(BaseModel):
    """Элемент ABC-анализа"""
    id: int
    sellerSku: str = Field(..., description="Артикул продавца")
    wbSku: str = Field(..., description="Артикул WB")
    revenue: float = Field(0, description="Выручка")
    profit: float = Field(0, description="Прибыль")
    share: float = Field(0, description="Доля %")
    cumulativePercent: float = Field(0, description="Совокупный %")
    category: str = Field(..., description="Категория A/B/C")


class TopProductSchema(BaseModel):
    """Топ товар"""
    id: int
    name: str
    vendor_code: Optional[str]
    sale_price: Optional[float]
    main_image_url: Optional[str]
    sales: int
    rating: Optional[float]
    revenue: Optional[float]


class LowStockProductSchema(BaseModel):
    """Товар с низким остатком"""
    id: int
    name: str
    vendor_code: Optional[str]
    total_quantity: int
    sale_price: Optional[float]


# ========== Схемы для Dashboard ==========

class MetricValueSchema(BaseModel):
    """Значение метрики с изменением"""
    value: float | int
    change_percent: float = Field(0, description="Изменение %")
    change_abs: float | int = Field(0, description="Изменение абсолютное")


class DashboardStatsSchema(BaseModel):
    """Статистика dashboard"""
    ordered_amount: MetricValueSchema
    ordered_units: MetricValueSchema
    revenue: MetricValueSchema
    sold_units: MetricValueSchema
    to_pay: MetricValueSchema
    profit: MetricValueSchema
    buyout_rate: MetricValueSchema
    avg_price: MetricValueSchema


class ChartDataPointSchema(BaseModel):
    """Точка данных для графика"""
    date: str
    orders: float
    buyouts: float
    avg_price: float
    profit: float
    margin: float
    views: int
    clicks: int
    cart: int
    cr: float  # Conversion rate
    ctr: float  # Click-through rate
    drr: float  # Delivery return rate


class BaseCabinetStatsSchema(BaseModel):
    """Основные показатели кабинета"""
    adViews: int = Field(0, description="Просмотры рекламы")
    clicks: int = Field(0, description="Клики")
    clicksPercentage: float = Field(0, description="% кликов")
    addToCart: int = Field(0, description="Добавлено в корзину")
    addToCartPercentage: float = Field(0, description="% в корзину")
    orderedTotalCount: int = Field(0, description="Заказано всего (шт)")
    orderedTotalAmount: float = Field(0, description="Заказано всего (сумма)")
    boughtTotalCount: int = Field(0, description="Выкуплено всего (шт)")
    boughtTotalAmount: float = Field(0, description="Выкуплено всего (сумма)")
    buyoutPercent: float = Field(0, description="% выкупа")
    avgOrderValue: float = Field(0, description="Средний чек")
    marginality: float = Field(0, description="Маржинальность %")
    expenseRatio: float = Field(0, description="Доля расходов %")
    profit: float = Field(0, description="Прибыль")
    revenue: float = Field(0, description="Выручка")
    logistics: float = Field(0, description="Логистика")
    storage: float = Field(0, description="Хранение")


class SelectedProductSchema(BaseModel):
    """Выбранный товар для отображения"""
    id: int
    name: str
    price: str
    image: str
    sales: int
    rating: float


class DashboardResponseSchema(BaseModel):
    """Ответ dashboard"""
    is_synced: bool = Field(..., description="Синхронизированы ли данные")
    stats: Optional[DashboardStatsSchema] = None
    chartData: Optional[List[ChartDataPointSchema]] = None
    baseStats: Optional[BaseCabinetStatsSchema] = None
    warehouseData: Optional[List[WarehouseStatSchema]] = None
    abcAnalysis: Optional[List[AbcAnalysisItemSchema]] = None
    sizeChart: Optional[List[SizeDistributionSchema]] = None
    selectedProducts: Optional[List[SelectedProductSchema]] = None
    products_count: Optional[int] = Field(None, description="Количество товаров")
    total_stock: Optional[int] = Field(None, description="Общий остаток")


# ========== Схемы для синхронизации ==========

class SyncStatusSchema(BaseModel):
    """Статус синхронизации"""
    is_synced: bool
    last_sync_at: Optional[datetime] = None
    last_sync_type: Optional[str] = None
    last_sync_status: Optional[str] = None
    products_count: int = 0
    message: Optional[str] = None


class SyncRequestSchema(BaseModel):
    """Запрос на синхронизацию"""
    sync_type: str = Field("full", description="Тип синхронизации: full, incremental, products, stocks")
    emulate: bool = Field(True, description="Эмулировать данные (пока нет токена)")


class SyncLogSchema(BaseModel):
    """Лог синхронизации"""
    id: UUID
    user_id: UUID
    sync_type: str
    status: str
    source: str
    products_loaded: int
    products_updated: int
    products_created: int
    products_deleted: int
    stocks_processed: int
    errors_count: int
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        from_attributes = True
