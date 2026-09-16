from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database

if TYPE_CHECKING:
    from models.tariffs_model import TariffPlan
    from models.users_model import User


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentProvider(str, Enum):
    FAKE = "fake"
    YOOKASSA = "yookassa"
    SBER = "sber"


class Payment(Database.Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            "idempotency_key",
            name="uq_payments_user_provider_idempotency",
        ),
        Index("ix_payments_external_payment_id", "external_payment_id"),
    )

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
        PG_UUID(as_uuid=True),
        ForeignKey("tariff_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(
        PgEnum(
            PaymentStatus,
            values_callable=lambda x: [e.value for e in x],
            name="payment_status",
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        PgEnum(
            PaymentProvider,
            values_callable=lambda x: [e.value for e in x],
            name="payment_provider",
        ),
        nullable=False,
        default=PaymentProvider.FAKE,
    )
    mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="live",
        comment="Provider mode snapshot at payment creation: test or live",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Client payment-attempt idempotency key; unique per user/provider",
    )
    external_payment_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Provider-side order/payment identifier",
    )
    provider_status: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Last normalized provider status",
    )
    provider_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Non-secret provider metadata needed for reconciliation",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the provider was server-side confirmed as paid",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User")
    tariff: Mapped["TariffPlan"] = relationship("TariffPlan")
    events: Mapped[list["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentEvent(Database.Base):
    __tablename__ = "payment_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Internal event name, e.g. registered/status_checked/callback",
    )
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    payment: Mapped[Payment] = relationship("Payment", back_populates="events")
