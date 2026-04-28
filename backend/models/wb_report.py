from datetime import date, datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database

class WbRealizationReport(Database.Base):
    __tablename__ = 'wb_realization_reports'

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

    # привязка к токену
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('api_tokens.id', ondelete='CASCADE'),
        nullable=False,
        server_default=text('gen_random_uuid()'),
        index=True
    )
    
    # ========== Ключевые даты (из официального ответа API) ==========
    
    # Дата отчёта (ключевое поле для агрегации по дням!)
    rr_dt: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )
    
    # Дата заказа
    order_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Дата продажи
    sale_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Период отчёта
    date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Дата создания отчёта
    create_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # ========== Идентификаторы ==========
    
    # Артикул товара (nmID)
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    # ID строки отчёта (уникальный идентификатор записи)
    rrd_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True
    )
    
    # ID отчёта о реализации
    realizationreport_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    # ID поставки
    gi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Уникальный идентификатор заказа
    srid: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )
    
    # UID заказа
    order_uid: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # ID сборки
    assembly_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # ID штрихкода
    shk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # ========== Типы операций и документов ==========
    
    # Тип операции: "Продажа", "Возврат", "Логистика" и т.д.
    supplier_oper_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    # Тип документа
    doc_type_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # ========== Товарные данные ==========
    
    # Категория товара
    subject_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Бренд
    brand_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Артикул продавца
    sa_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Размер
    ts_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Штрихкод
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # КИЗ (код идентификации продукции)
    kiz: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Склад
    office_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # ========== Финансовые данные ==========
    
    # Сумма продажи/возврата
    retail_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Розничная цена
    retail_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Цена с учётом скидки
    retail_price_withdisc_rub: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Количество единиц
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Количество доставок
    delivery_amount: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Количество возвратов
    return_amount: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Комиссия маркетплейса
    ppvz_sales_commission: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Стоимость доставки
    delivery_rub: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Стоимость возврата логистики
    """ return_rub: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    ) """
    
    # Штрафы
    penalty: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Прочие удержания
    additional_payment: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Плата за хранение
    storage_fee: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # К перечислению
    ppvz_for_pay: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # Вознаграждение
    ppvz_reward: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Комиссия за эквайринг
    acquiring_fee: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # ========== Проценты и скидки ==========
    
    # Процент скидки
    sale_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Процент комиссии
    commission_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Процент СПП
    ppvz_spp_prc: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Базовый процент КВВ
    ppvz_kvw_prc_base: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Процент КВВ
    ppvz_kvw_prc: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # Процент ВВ
    ppvz_vw: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # НДС ВВ
    ppvz_vw_nds: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    
    # ========== Для аудита ==========
    
    # Дата создания записи в БД
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    __table_args__ = (
        # Уникальный индекс по уникальному идентификатору строки отчёта
        Index('uq_wb_realization_rrd_id', 'rrd_id', unique=True),
        
        # Индекс для быстрого поиска по периоду и пользователю
        Index('idx_wb_realization_user_rrdt', 'user_id', 'rr_dt'),
        
        # Индекс для поиска по артикулу и дате
        Index('idx_wb_realization_user_nm_rrdt', 'user_id', 'nm_id', 'rr_dt'),
    )

    def __repr__(self):
        return (
            f"<WbRealizationReport("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"rr_dt={self.rr_dt}, "
            f"nm_id={self.nm_id}, "
            f"type={self.supplier_oper_name}, "
            f"amount={self.retail_amount}"
            f")>"
        )

    @property
    def is_sale(self) -> bool:
        """Проверка, является ли операция продажей"""
        return self.operation_type.lower() in ["продажа", "продажа (пр)", "Продажа"]

    @property
    def is_return(self) -> bool:
        """Проверка, является ли операция возвратом"""
        return self.operation_type.lower() in ["возврат", "возврат (пр)", "Возврат"]

    @property
    def is_logistics(self) -> bool:
        """Проверка, является ли операция логистикой"""
        return "логистика" in self.operation_type.lower()

    @property
    def net_revenue(self) -> float:
        """Чистая выручка (сумма - комиссия - логистика)"""
        return float(self.retail_amount - self.commission - self.delivery_rub)
