import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as PgEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tariff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tariff_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
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
        default=SubscriptionStatus.DEMO,
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Legacy compatibility field. New acquiring integrations must use payment_id.
    yookassa_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    tariff: Mapped["TariffPlan"] = relationship("TariffPlan", back_populates="subscriptions")

    @property
    def is_active(self) -> bool:
        if self.status not in {SubscriptionStatus.DEMO, SubscriptionStatus.ACTIVE}:
            return False
        now = datetime.now(timezone.utc)
        start = self.current_period_start
        end = self.current_period_end
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return start <= now <= end
