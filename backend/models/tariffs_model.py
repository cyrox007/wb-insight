from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID as UUIDType

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Numeric,
    func,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database
from models.subscription_model import Subscription


class TariffPlan(Database.Base):
    __tablename__ = "tariff_plans"

    # comment="Уникальный идентификатор"
    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4,
    )	
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Код тарифа: 'demo', 'starter', 'pro', 'enterprise'"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Отображаемое название: 'Демо', 'Старт (для ИП)', 'Про', 'Бизнес'"
    )
    description: Mapped[str] = mapped_column(
        Text,
        comment='Описание для лендинга: "7 дней бесплатно, без карты"'
    )
    price_rub: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Цена в рублях за месяц (0.00 для демо)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли тариф (можно скрыть без удаления)"
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),  # 🔥 ВАЖНО
        comment="Доступен ли тариф для выбора пользователями"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Когда создан"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Последнее изменение цены/лимитов"
    )

    subscriptions: Mapped["Subscription"] = relationship("Subscription", back_populates="tariff")

    limits: Mapped[list["TariffLimit"]] = relationship("TariffLimit", back_populates='tariff')

    def __repr__(self):
        return (
            f"<TariffPlan("
            f"id={self.id}, "
            f"code={self.code}, "
            f"name={self.name}")
    

class TariffLimit(Database.Base):
    __tablename__ = "tariff_limits"

    tariff_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tariff_plans.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на тариф"
    )
    limit_type: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="Тип лимита: 'wb_accounts', 'nm_ids', 'sync_frequency_hours', 'ai_queries_per_month', 'retention_days'"
    )
    limit_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Числовое значение лимита"
    )

    tariff: Mapped["TariffPlan"] = relationship("TariffPlan", back_populates="limits")

    def __repr__(self):
        return f"TariffLimit<{self.tariff_id}>"
