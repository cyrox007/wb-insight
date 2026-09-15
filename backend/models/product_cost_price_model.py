from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, UUID as PG_UUID, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class ProductCostPrice(Database.Base):
    """Latest cost-price snapshot for a user's WB article.

    Historical versions live in ProductCostPriceHistory. Keeping this table as
    a single-row snapshot preserves the existing UI/API lookup contract.
    """

    __tablename__ = 'product_cost_prices'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    nm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    seller_sku: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cost_price: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default='RUB', nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'nm_id', name='uq_user_nm_cost_price'),
        Index('idx_product_cost_user_nm', 'user_id', 'nm_id'),
        Index('idx_product_cost_seller_sku', 'seller_sku'),
        Index('idx_product_cost_effective', 'user_id', 'nm_id', 'effective_from'),
    )

    def __repr__(self):
        return (
            f"<ProductCostPrice("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"nm_id={self.nm_id}, "
            f"cost_price={self.cost_price}, "
            f"effective_from={self.effective_from}"
            f")>"
        )
