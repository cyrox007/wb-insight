from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbSalesFunnelDaily(Database.Base):
    """Daily seller-analytics funnel fact at marketplace account/product grain."""

    __tablename__ = "wb_sales_funnel_daily"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    nm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    vendor_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subject_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cart_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    buyout_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyout_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    buyout_percent: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    add_to_cart_conversion: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0
    )
    cart_to_order_conversion: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0
    )
    add_to_wishlist_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
            "token_id", "nm_id", "date", name="uq_wb_sales_funnel_account_nm_date"
        ),
        Index("idx_wb_sales_funnel_user_date", "user_id", "date"),
        Index("idx_wb_sales_funnel_token_date", "token_id", "date"),
        Index("idx_wb_sales_funnel_nm_date", "nm_id", "date"),
    )
