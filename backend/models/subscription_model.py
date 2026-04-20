from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as PgEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from database import Database


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
    status: Mapped[SubscriptionStatus] = mapped_column(
        PgEnum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE
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
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)

        return (
            self.status == SubscriptionStatus.ACTIVE
            and self.current_period_end > now
        )
