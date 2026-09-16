from datetime import date as dt_date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbPaidStorage(Database.Base):
    """Wildberries paid-storage source fact.

    WB does not expose a stable row identifier for this report. A completed
    report chunk is therefore replaced atomically for its account/date range
    instead of relying on a guessed uniqueness key.
    """

    __tablename__ = "wb_paid_storage"

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
    source_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    date: Mapped[dt_date] = mapped_column(Date, nullable=False, index=True)
    log_warehouse_coef: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    office_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    warehouse_coef: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    gi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chrt_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vendor_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nm_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    calc_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    warehouse_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    barcodes_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pallet_place_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pallet_count: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    original_date: Mapped[Optional[dt_date]] = mapped_column(Date, nullable=True)
    loyalty_discount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    tariff_fix_date: Mapped[Optional[dt_date]] = mapped_column(Date, nullable=True)
    tariff_lower_date: Mapped[Optional[dt_date]] = mapped_column(Date, nullable=True)

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
        Index("idx_wb_paid_storage_user_date", "user_id", "date"),
        Index("idx_wb_paid_storage_token_date", "token_id", "date"),
        Index("idx_wb_paid_storage_nm_date", "nm_id", "date"),
    )
