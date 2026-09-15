from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as PgEnum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database

if TYPE_CHECKING:
    from models.tariffs_model import TariffPlan
    from models.users_model import User


class SubscriptionStatus(str, Enum):
    DEMO = "demo"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Subscription(Database.Base):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tariff_id: Mapped[UUID] = mapped_column(
        ForeignKey("tariff_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        comment="Confirmed payment that activated this subscription",
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        PgEnum(
            SubscriptionStatus,
            values_callable=lambda x: [e.value for e in x],
            name="subscription_status",
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Начало текущего оплаченного периода",
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Конец текущего оплаченного периода",
    )
    yookassa_payment_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ID платежа в ЮKassa (null для демо-подписок)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Дата оформления подписки",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Последнее обновление статуса или периода",
    )

    tariff: Mapped["TariffPlan"] = relationship("TariffPlan", back_populates="subscriptions")
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"Subscription<{self.id}>"

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.DEMO}
            and self.current_period_start <= now < self.current_period_end
        )
