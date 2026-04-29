from datetime import datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import UUID as PG_UUID, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class ProductCostPrice(Database.Base):
    """
    Таблица для хранения закупочных цен (себестоимости) товаров

    Позволяет хранить стоимость единицы товара для расчёта:
    - Прибыли: profit = ppvz_for_pay - (cost_price × quantity)
    - Маржинальности: margin = profit / retail_amount × 100
    - DRR: (commission + logistics + penalty) / retail_amount × 100
    """

    __tablename__ = 'product_cost_prices'

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

    # Артикул WB товара (nmID)
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    # Артикул продавца (для удобства работы)
    seller_sku: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )

    # Наименование товара (кэш из отчёта)
    product_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Себестоимость единицы товара (в рублях)
    cost_price: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # Валюта себестоимости
    currency: Mapped[str] = mapped_column(
        String(10),
        default='RUB',
        nullable=False
    )

    # Комментарий (опционально)
    comment: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Дата последнего обновления
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Дата создания записи
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        # Уникальность комбинации user_id + nm_id
        UniqueConstraint('user_id', 'nm_id', name='uq_user_nm_cost_price'),

        # Индекс для быстрого поиска по пользователю и артикулу
        Index('idx_product_cost_user_nm', 'user_id', 'nm_id'),

        # Индекс для поиска по артикулу продавца
        Index('idx_product_cost_seller_sku', 'seller_sku'),
    )

    def __repr__(self):
        return (
            f"<ProductCostPrice("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"nm_id={self.nm_id}, "
            f"cost_price={self.cost_price}"
            f")>"
        )