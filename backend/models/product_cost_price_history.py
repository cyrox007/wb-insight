from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class ProductCostPriceHistory(Database.Base):
    """Immutable cost-price version effective from a calendar date."""

    __tablename__ = "product_cost_price_history"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    seller_sku: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cost_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "nm_id",
            "effective_from",
            name="uq_product_cost_history_user_nm_effective",
        ),
        Index(
            "idx_product_cost_history_lookup",
            "user_id",
            "nm_id",
            "effective_from",
        ),
    )
