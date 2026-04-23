from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Numeric,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbStock(Database.Base):
    __tablename__ = "wb_stocks"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # 🔗 привязка
    user_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    token_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    # 📦 идентификация товара
    nm_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    barcode: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    supplier_article: Mapped[Optional[str]] = mapped_column(String(100))

    # 📍 склад
    warehouse_name: Mapped[str] = mapped_column(String(100), index=True)

    # 📊 остатки
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    quantity_full: Mapped[int] = mapped_column(Integer, default=0)
    in_way_to_client: Mapped[int] = mapped_column(Integer, default=0)
    in_way_from_client: Mapped[int] = mapped_column(Integer, default=0)

    # 💰 цена
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    discount: Mapped[Optional[int]] = mapped_column(Integer)

    # 📦 доп поля
    category: Mapped[Optional[str]] = mapped_column(String(100))
    subject: Mapped[Optional[str]] = mapped_column(String(100))
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    tech_size: Mapped[Optional[str]] = mapped_column(String(50))

    is_supply: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_realization: Mapped[Optional[bool]] = mapped_column(Boolean)
    sc_code: Mapped[Optional[str]] = mapped_column(String(50))

    # ⏱ WB время изменения
    last_change_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False
    )

    # ⏱ обновление у нас
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    __table_args__ = (
        # 🔥 КРИТИЧНО: уникальность
        UniqueConstraint(
            "token_id",
            "nm_id",
            "warehouse_name",
            "barcode",
            name="uq_wb_stock_unique"
        ),

        # 🔍 индексы
        Index("idx_wb_stock_user_nm", "user_id", "nm_id"),
        Index("idx_wb_stock_token_nm", "token_id", "nm_id"),
    )

    def __repr__(self):
        return f"<WbStock nm_id={self.nm_id} warehouse={self.warehouse_name} qty={self.quantity}>"