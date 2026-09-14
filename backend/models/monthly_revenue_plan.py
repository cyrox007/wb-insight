from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class MonthlyRevenuePlan(Database.Base):
    """User-defined monthly revenue target for one marketplace account."""

    __tablename__ = "monthly_revenue_plans"

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
    month: Mapped[date] = mapped_column(Date, nullable=False)
    revenue_target: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "token_id",
            "month",
            name="uq_monthly_revenue_plan_user_token_month",
        ),
        CheckConstraint(
            "revenue_target > 0",
            name="ck_monthly_revenue_plan_positive_target",
        ),
        Index("ix_monthly_revenue_plans_user_month", "user_id", "month"),
    )
