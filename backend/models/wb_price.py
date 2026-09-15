from datetime import datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbPriceCurrent(Database.Base):
    """Latest read-only WB price snapshot for one product size."""

    __tablename__ = "wb_price_current"

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
    size_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vendor_code: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tech_size_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    base_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    discounted_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    club_discounted_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    club_discount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    editable_size_price: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_bad_turnover: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "token_id",
            "nm_id",
            "size_id",
            name="uq_wb_price_current_account_nm_size",
        ),
        Index("ix_wb_price_current_user_nm", "user_id", "nm_id"),
    )


class WbPriceChange(Database.Base):
    """Old/new price values recorded only when WB snapshot changes."""

    __tablename__ = "wb_price_history"

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
    size_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vendor_code: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tech_size_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    previous_base_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    base_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    previous_discounted_price: Mapped[float] = mapped_column(
        Numeric(15, 2), nullable=False
    )
    discounted_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    previous_club_discounted_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    club_discounted_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    previous_discount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    previous_club_discount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    club_discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_wb_price_history_token_changed", "token_id", "changed_at"),
        Index("ix_wb_price_history_nm_changed", "nm_id", "changed_at"),
    )
