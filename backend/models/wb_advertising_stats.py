from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbAdvertisingStats(Database.Base):
    """Daily WB Promotion fact at account/campaign/product/platform grain."""

    __tablename__ = "wb_advertising_stats"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
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

    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    platform_type: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    cpc: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    added_to_cart: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canceled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cr: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    shks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders_amount: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, nullable=False
    )
    avg_position: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), default=0, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_wb_adv_user_date", "user_id", "date"),
        Index("idx_wb_adv_token_date", "token_id", "date"),
        Index("idx_wb_adv_campaign_date", "campaign_id", "date"),
        Index("idx_wb_adv_user_nm_date", "user_id", "nm_id", "date"),
        Index(
            "idx_wb_adv_unique",
            "token_id",
            "campaign_id",
            "nm_id",
            "date",
            "platform_type",
            unique=True,
        ),
    )

    def __repr__(self):
        return (
            f"<WbAdvertisingStats(id={self.id}, token_id={self.token_id}, "
            f"campaign_id={self.campaign_id}, date={self.date}, nm_id={self.nm_id})>"
        )
