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
    
    # Уникальный идентификатор заказа
    srid: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )
    
    # ========== Типы операций и документов ==========
    
    # Тип операции: "Продажа", "Возврат", "Логистика" и т.д.
    supplier_oper_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    # ========== Товарные данные ==========
    
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
    
    # Количество единиц
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
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
    
    # К перечислению
    ppvz_for_pay: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )
    
    # ========== Проценты и скидки ==========
    
    # ========== Для аудита ==========
    
    # Дата создания записи в БД
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    __table_args__ = (
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
