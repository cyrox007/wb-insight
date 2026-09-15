from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbFinanceReportSummary(Database.Base):
    """Canonical WB sales-report summary used for payout reconciliation."""

    __tablename__ = "wb_finance_report_summaries"

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("api_tokens.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seller_finance_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_to: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    create_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    report_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    retail_amount_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    for_pay_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    avg_sale_percent: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    delivery_service_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    paid_storage_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    paid_acceptance_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    deduction_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    penalty_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    additional_payment_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cashback_amount_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cashback_discount_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cashback_commission_change_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    payment_schedule: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    bank_payment_sum: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    __table_args__ = (
        UniqueConstraint("token_id", "report_id", name="uq_wb_finance_report_account_report"),
        Index("ix_wb_finance_report_user_period", "user_id", "date_from", "date_to"),
        Index("ix_wb_finance_report_token_period", "token_id", "date_from", "date_to"),
    )


class WbFinanceBalanceCurrent(Database.Base):
    """Latest seller balance widget returned by the WB Finance API."""

    __tablename__ = "wb_finance_balance_current"

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("api_tokens.id", ondelete="CASCADE"), nullable=False, index=True
    )
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    current_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    for_withdraw: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    __table_args__ = (
        UniqueConstraint("token_id", name="uq_wb_finance_balance_account"),
        Index("ix_wb_finance_balance_user", "user_id"),
    )
