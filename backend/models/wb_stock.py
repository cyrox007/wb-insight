from datetime import datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbStock(Database.Base):
    __tablename__ = "wb_stocks"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # One WB inventory response row represents one size in one warehouse.
    nm_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    chrt_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    warehouse_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    warehouse_name: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    region_name: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    in_way_to_client: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    in_way_from_client: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    price = mapped_column(Numeric(12, 2), nullable=True)

    # Kept only for rows imported through the deprecated statistics endpoint.
    # The current analytics endpoint does not return lastChangeDate.
    last_change_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "token_id",
            "nm_id",
            "chrt_id",
            "warehouse_id",
            name="uq_wb_stock_ui",
        ),
    )

    def __repr__(self):
        return (
            f"<WbStock nm_id={self.nm_id} chrt_id={self.chrt_id} "
            f"warehouse={self.warehouse_name} qty={self.quantity}>"
        )
