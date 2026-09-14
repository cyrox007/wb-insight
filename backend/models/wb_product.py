from datetime import datetime, timezone
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbProduct(Database.Base):
    __tablename__ = 'wb_product'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

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

    __table_args__ = (
        UniqueConstraint('token_id', 'nm_id', name='uq_wb_product_account_nm'),
    )

    def __repr__(self):
        return (
            f"<WbProductCard(id={self.id}, user_id={self.user_id}, "
            f"nm_id={self.nm_id})>"
        )
