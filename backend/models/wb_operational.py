from datetime import datetime, timezone
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


class WbOrder(Database.Base):
    __tablename__ = "wb_orders"

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

    srid: Mapped[str] = mapped_column(String(200), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_change_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    warehouse_name: Mapped[str | None] = mapped_column(String(200))
    warehouse_type: Mapped[str | None] = mapped_column(String(100))
    country_name: Mapped[str | None] = mapped_column(String(100))
    oblast_okrug_name: Mapped[str | None] = mapped_column(String(200))
    region_name: Mapped[str | None] = mapped_column(String(200))

    supplier_article: Mapped[str | None] = mapped_column(String(200))
    nm_id: Mapped[int | None] = mapped_column(Integer, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(200))
    tech_size: Mapped[str | None] = mapped_column(String(100))

    income_id: Mapped[int | None] = mapped_column(BigInteger)
    is_supply: Mapped[bool | None] = mapped_column(Boolean)
    is_realization: Mapped[bool | None] = mapped_column(Boolean)

    total_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    discount_percent: Mapped[float | None] = mapped_column(Numeric(10, 4))
    spp: Mapped[float | None] = mapped_column(Numeric(10, 4))
    finished_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    price_with_disc: Mapped[float | None] = mapped_column(Numeric(15, 2))

    is_cancel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancel_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sticker: Mapped[str | None] = mapped_column(String(100))
    g_number: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("token_id", "srid", name="uq_wb_order_account_srid"),
        Index("ix_wb_orders_user_date", "user_id", "order_date"),
        Index("ix_wb_orders_token_change", "token_id", "last_change_date"),
    )


class WbSale(Database.Base):
    __tablename__ = "wb_sales"

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

    sale_id: Mapped[str] = mapped_column(String(100), nullable=False)
    srid: Mapped[str | None] = mapped_column(String(200), index=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_change_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    warehouse_name: Mapped[str | None] = mapped_column(String(200))
    warehouse_type: Mapped[str | None] = mapped_column(String(100))
    country_name: Mapped[str | None] = mapped_column(String(100))
    oblast_okrug_name: Mapped[str | None] = mapped_column(String(200))
    region_name: Mapped[str | None] = mapped_column(String(200))

    supplier_article: Mapped[str | None] = mapped_column(String(200))
    nm_id: Mapped[int | None] = mapped_column(Integer, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(200))
    tech_size: Mapped[str | None] = mapped_column(String(100))

    income_id: Mapped[int | None] = mapped_column(BigInteger)
    is_supply: Mapped[bool | None] = mapped_column(Boolean)
    is_realization: Mapped[bool | None] = mapped_column(Boolean)

    total_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    discount_percent: Mapped[float | None] = mapped_column(Numeric(10, 4))
    spp: Mapped[float | None] = mapped_column(Numeric(10, 4))
    payment_sale_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    for_pay: Mapped[float | None] = mapped_column(Numeric(15, 2))
    finished_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    price_with_disc: Mapped[float | None] = mapped_column(Numeric(15, 2))

    sticker: Mapped[str | None] = mapped_column(String(100))
    g_number: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("token_id", "sale_id", name="uq_wb_sale_account_sale_id"),
        Index("ix_wb_sales_user_date", "user_id", "sale_date"),
        Index("ix_wb_sales_token_change", "token_id", "last_change_date"),
    )
