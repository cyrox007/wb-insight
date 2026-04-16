from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Numeric,
    func
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


class TariffPlan(Database.Base):
    __tablename__ = "tariff_plans"

    # comment="Уникальный идентификатор"
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
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

    def __repr__(self):
        return (
            f"<TariffPlan("
            f"id={self.id}, "
            f"code={self.code}, "
            f"name={self.name}")
    

class TariffLimit(Database.Base):
    __tablename__ = "tariff_limits"

    tariff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tariff_plans.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на тариф"
    )
    limit_type = Column(
        String(50),
        primary_key=True,
        comment="Тип лимита: 'wb_accounts', 'nm_ids', 'sync_frequency_hours', 'ai_queries_per_month', 'retention_days'"
    )
    limit_value = Column(
        Integer,
        nullable=False,
        comment="Числовое значение лимита"
    )

    def __repr__(self):
        return f"TariffLimit<{self.tariff_id}>"
    

class SubscriptionStatus(str, Enum):
    DEMO = "demo"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"    

class Subscription(Database.Base):
    __tablename__ = "subscriptions"

    # comment="Уникальный идентификатор подписки"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # comment="Владелец подписки"
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # comment="Текущий тариф"
    tariff_id: Mapped[UUID] = mapped_column(
        ForeignKey("tariff_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # comment="Статус: 'active', 'expired', 'cancelled', 'demo'"
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active"
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Начало текущего оплаченного периода"
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Конец текущего оплаченного периода"
    )
    yookassa_payment_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ID платежа в ЮKassa (null для демо-подписок)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Дата оформления подписки"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Последнее обновление статуса или периода"
    )

    def __repr__(self):
        return "Subscription<{}>".format(self.id)
    
    @property
    async def is_subscription_active(self) -> bool:
        return self.current_period_end > datetime.utcnow()
