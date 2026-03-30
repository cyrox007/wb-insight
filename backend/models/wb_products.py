from datetime import date, datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Database


class WbProduct(Database.Base):
    """
    Модель товара пользователя из Wildberries.
    
    Хранит основную информацию о товаре: артикулы, название, бренд, категорию,
    цены, фотографии и другие характеристики.
    """
    __tablename__ = 'wb_products'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Привязка к пользователю
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========== Идентификаторы ==========

    # Артикул WB (nmID) - основной идентификатор товара на маркетплейсе
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    # Артикул продавца (vendor code)
    vendor_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    
    # Штрихкод (может быть несколько, но храним основной)
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    
    # ========== Товарные данные ==========\n    
    # Название товара
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    # Бренд
    brand: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )
    
    # Категория товара
    category: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )
    
    # Подкатегория
    subcategory: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Описание товара
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ========== Цены ==========\n    
    # Розничная цена (цена до скидок)
    retail_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Цена продажи (текущая цена с учётом скидок)
    sale_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Скидка в процентах
    discount_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Закупочная цена (для расчёта прибыли)
    purchase_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # НДС в процентах
    vat_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # ========== Характеристики ==========\n    
    # Размер
    size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Цвет
    color: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Вес товара (в граммах)
    weight: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Габариты упаковки (ДхШхВ в см)
    dimensions: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Объем в литрах
    volume: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )
    
    # ========== Статусы ==========\n    
    # Активен ли товар
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )
    
    # Архивирован ли товар
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    
    # Статус модерации
    moderation_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # ========== Фотографии ==========\n    
    # URL главной фотографии
    main_image_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True
    )
    
    # Количество фотографий
    images_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # ========== Рейтинги и отзывы ==========\n    
    # Рейтинг товара
    rating: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True
    )
    
    # Количество отзывов
    reviews_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество вопросов
    questions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # ========== Продажи (агрегированные данные) ==========\n    
    # Количество заказов за всё время
    total_orders: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество продаж за всё время
    total_sales: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Выручка за всё время
    total_revenue: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )
    
    # ========== Даты ==========\n    
    # Дата создания карточки товара
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )
    
    # Дата последнего обновления данных
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=False
    )
    
    # Дата первой продажи
    first_sale_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Дата последней продажи
    last_sale_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )

    # Связь с остатками
    stocks: Mapped[list["WbProductStock"]] = relationship(
        "WbProductStock",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        # Уникальный индекс по nm_id для пользователя
        Index('uq_wb_products_user_nm', 'user_id', 'nm_id', unique=True),
        
        # Индекс для поиска по артикулу продавца
        Index('idx_wb_products_vendor_code', 'user_id', 'vendor_code'),
        
        # Индекс для активных товаров
        Index('idx_wb_products_active', 'user_id', 'is_active'),
        
        # Индекс для категории и бренда
        Index('idx_wb_products_category_brand', 'user_id', 'category', 'brand'),
    )

    def __repr__(self):
        return (
            f"<WbProduct("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"nm_id={self.nm_id}, "
            f"name={self.name[:30]}..., "
            f"price={self.sale_price}"
            f")>"
        )

    @property
    def has_discount(self) -> bool:
        """Проверка наличия скидки"""
        return self.discount_percent is not None and self.discount_percent > 0

    @property
    def profit_margin(self) -> Optional[float]:
        """Маржинальность в процентах (прибыль / цена продажи * 100)"""
        if self.sale_price and self.purchase_price and self.sale_price > 0:
            return round(((self.sale_price - self.purchase_price) / self.sale_price) * 100, 2)
        return None

    @property
    def profit_amount(self) -> Optional[float]:
        """Прибыль с единицы товара"""
        if self.sale_price and self.purchase_price:
            return round(self.sale_price - self.purchase_price, 2)
        return None


class WbProductStock(Database.Base):
    """
    Модель остатков товара на складах Wildberries.
    
    Хранит информацию о количестве товара на каждом складе,
    включая товары в пути.
    """
    __tablename__ = 'wb_product_stocks'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Привязка к товару
    product_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('wb_products.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Привязка к пользователю (для удобных запросов)
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========== Идентификаторы ==========\n    
    # Артикул WB
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    # Штрихкод
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # ========== Склад ==========\n    
    # Название склада
    warehouse_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )
    
    # ID склада
    warehouse_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Регион склада
    region: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # ========== Остатки ==========\n    
    # Количество на складе
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество в пути
    quantity_in_transit: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Резерв (заказано, но ещё не отгружено)
    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Доступное количество (quantity - reserved)
    quantity_available: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # ========== Даты ==========\n    
    # Дата последнего обновления остатков
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=False
    )

    # Обратная связь с товаром
    product: Mapped["WbProduct"] = relationship(
        "WbProduct",
        back_populates="stocks"
    )

    __table_args__ = (
        # Уникальный индекс по товару и складу
        Index('uq_wb_stocks_product_warehouse', 'product_id', 'warehouse_name', unique=True),
        
        # Индекс для поиска по пользователю и складу
        Index('idx_wb_stocks_user_warehouse', 'user_id', 'warehouse_name'),
        
        # Индекс для товаров с малым остатком
        Index('idx_wb_stocks_low_quantity', 'user_id', 'quantity'),
    )

    def __repr__(self):
        return (
            f"<WbProductStock("
            f"id={self.id}, "
            f"product_id={self.product_id}, "
            f"warehouse={self.warehouse_name}, "
            f"qty={self.quantity}"
            f")>"
        )

    @property
    def total_quantity(self) -> int:
        """Общее количество (на складе + в пути)"""
        return self.quantity + self.quantity_in_transit


class ProductSyncLog(Database.Base):
    """
    Лог синхронизации товаров.
    
    Используется для отслеживания истории синхронизаций,
    отладки и мониторинга процесса обновления данных.
    """
    __tablename__ = 'product_sync_logs'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Привязка к пользователю
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========== Информация о синхронизации ==========\n    
    # Тип синхронизации
    sync_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="full - полная, incremental - частичная, products - только товары, stocks - только остатки"
    )
    
    # Статус синхронизации
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="pending, in_progress, success, partial, failed"
    )
    
    # Источник данных
    source: Mapped[str] = mapped_column(
        String(50),
        default="wildberries_api",
        nullable=False,
        comment="wildberries_api, manual, emulation"
    )
    
    # ========== Статистика ==========\n    
    # Количество загруженных товаров
    products_loaded: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество обновлённых товаров
    products_updated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество созданных товаров
    products_created: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество удалённых товаров
    products_deleted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество обработанных остатков
    stocks_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество ошибок
    errors_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # ========== Ошибки ==========\n    
    # Сообщение об ошибке (если есть)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Детали ошибки (JSON или текст)
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ========== Время ==========\n    
    # Начало синхронизации
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )
    
    # Завершение синхронизации
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Длительность в секундах
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )

    __table_args__ = (
        # Индекс для поиска по пользователю и дате
        Index('idx_product_sync_user_started', 'user_id', 'started_at'),
        
        # Индекс для поиска по статусу
        Index('idx_product_sync_status', 'status'),
        
        # Индекс для последних синхронизаций
        Index('idx_product_sync_recent', 'user_id', 'started_at', 'status'),
    )

    def __repr__(self):
        return (
            f"<ProductSyncLog("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.sync_type}, "
            f"status={self.status}"
            f")>"
        )

    @property
    def is_completed(self) -> bool:
        """Завершена ли синхронизация"""
        return self.status in ['success', 'partial', 'failed']

    @property
    def is_successful(self) -> bool:
        """Успешна ли синхронизация"""
        return self.status == 'success'
