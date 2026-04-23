from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbProductCard(Database.Base):
    __tablename__ = 'wb_product_cards'

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

    # Основные поля
    nm_id: Mapped[int] = mapped_column(  # ← nm_id (snake_case, без заглавных)
        Integer,
        nullable=False,
        index=True
    )  # Артикул WB

    nm_uuid: Mapped[str] = mapped_column(  # ← snake_case
        String(36),  # UUID имеет фиксированную длину 36 символов
        nullable=False
    )  # Внутренний технический ID карточки товара

    subject_id: Mapped[int] = mapped_column(  # ← snake_case
        Integer,
        nullable=False,
        index=True
    )  # ID предмета

    subject_name: Mapped[str] = mapped_column(  # ← snake_case
        String(255),
        nullable=True,
        index=True
    )  # Название предмета

    vendor_code: Mapped[str] = mapped_column(
        String(255), 
        nullable=True, 
        index=True
    ) # Артикул продавца

    brand: Mapped[str] = mapped_column(
        String(255), nullable=True
    ) # Бренд

    title: Mapped[str] = mapped_column(
        Text, nullable=False
    ) # Название товара

    description: Mapped[str] = mapped_column(
        Text, nullable=False
    ) # Описание товара

    photos: Mapped[str] = mapped_column(Text, nullable=True) # JSON массив URL

    characteristics: Mapped[str] = mapped_column(Text, nullable=True) # JSON массив характеристик

    # Для отслеживания обновлений
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now()
    )

    # Уникальный индекс: один артикул у одного пользователя
    __table_args__ = (
        Index('uq_wb_product_user_nmid', 'user_id', 'nm_id', unique=True),
        Index('idx_wb_product_nm_uuid', 'nm_uuid'),  # опционально
    )

    def __repr__(self):
        return (f"<WbProductCard("
                f"id={self.id}, "
                f"user_id={self.user_id}, "
                f"nm_id={self.nm_id}, "
                f"nm_uuid={self.nm_uuid})"
                f"title={self.title}, "
                ")>")