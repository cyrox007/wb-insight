from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, Numeric

from core.database import Database

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    func,
    Enum as PgEnum
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentProvider(str, Enum):
    FAKE = "fake"
    YOOKASSA = "yookassa"

class Payment(Database.Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # какой тариф покупали
    tariff_id: Mapped[UUID] = mapped_column(
        ForeignKey("tariff_plans.id", ondelete="RESTRICT"),
        nullable=False
    )

    # сумма
    amount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        default="RUB"
    )

    # статус
    status: Mapped[PaymentStatus] = mapped_column(
        PgEnum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=PaymentStatus.PENDING
    )

    # провайдер
    provider: Mapped[PaymentProvider] = mapped_column(
        PgEnum(
            PaymentProvider,
            name="payment_provider",
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=PaymentProvider.FAKE
    )

    # ID в платежной системе (ЮKassa и т.д.)
    external_payment_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # сырые данные от провайдера (очень важно)
    provider_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"Payment<{self.id}>"