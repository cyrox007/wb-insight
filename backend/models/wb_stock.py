from datetime import datetime
from uuid import uuid4, UUID as UUIDType

from sqlalchemy import (
    String, Integer, DateTime, Numeric,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbStock(Database.Base):
    __tablename__ = "wb_stocks"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # 🔗 привязка
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    token_id: Mapped[UUIDType] = mapped_column(
        String(36),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    # 📍 идентификаторы склада
    nm_id = mapped_column(Integer, index=True)
    warehouse_id = mapped_column(Integer, index=True)
    warehouse_name = mapped_column(String(100), index=True)

    # 📦 остатки (уже агрегированные)
    quantity = mapped_column(Integer, default=0)
    in_way_to_client = mapped_column(Integer, default=0)
    in_way_from_client = mapped_column(Integer, default=0)

    # 💰 (опционально, если считаешь в UI)
    price = mapped_column(Numeric(12, 2), nullable=True)

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
        UniqueConstraint(
            "token_id",
            "nm_id",
            "warehouse_id",
            name="uq_wb_stock_ui"
        ),
    )

    def __repr__(self):
        return f"<WbStock nm_id={self.nm_id} warehouse={self.warehouse_name} qty={self.quantity}>"