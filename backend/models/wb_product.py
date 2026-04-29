from datetime import datetime, timezone
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbProduct(Database.Base):
    __tablename__ = 'wb_product'

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
        index=True,
        comment="Привязка к пользователю"
    )

    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('api_tokens.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="привязка к токену кабинета"
    )

    # Основные поля
    nm_id: Mapped[int] = mapped_column(  
        Integer,
        nullable=False,
        index=True,
        comment="Артикул WB"
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Наименование товара"
    )

    # системное
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        comment='Создано'
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        comment='Обновлено'
    )

    def __repr__(self):
        return (f"<WbProductCard("
                f"id={self.id}, "
                f"user_id={self.user_id}, "
                f"nm_id={self.nm_id}, "
                ")>")