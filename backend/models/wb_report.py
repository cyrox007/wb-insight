from datetime import date, datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbRealizationReport(Database.Base):
    __tablename__ = 'wb_realization_reports'

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

    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('api_tokens.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    rr_dt: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_dt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sale_dt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    create_dt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    nm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rrd_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shk_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    srid: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    realization_report_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    supplier_oper_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    doc_type_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    subject_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    sa_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    ts_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    office_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gi_box_type_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ppvz_office_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ppvz_office_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retail_price: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    retail_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    retail_price_with_disc_rub: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)

    sale_percent: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    commission_percent: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    product_discount_for_report: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    ppvz_spp_prc: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)

    ppvz_kvw_prc_base: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    ppvz_kvw_prc: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    sup_rating_prc_up: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)
    is_kgvp_v2: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=True)

    ppvz_sales_commission: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    ppvz_for_pay: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    ppvz_reward: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    ppvz_vw: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    ppvz_vw_nds: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)

    delivery_rub: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    return_rub: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    delivery_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    return_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    rebill_logistic_cost: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    rebill_logistic_org: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    storage_fee: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    acceptance: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)

    penalty: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    additional_payment: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    deduction: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    acquiring_fee: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    acquiring_bank: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    supplier_promo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    order_uid: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    kiz: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    declaration_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    ppvz_supplier_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ppvz_supplier_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    ppvz_inn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    currency_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    report_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trbx_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint('token_id', 'rrd_id', name='uq_wb_realization_token_rrd'),
        Index('idx_wb_realization_user_rrdt', 'user_id', 'rr_dt'),
        Index('idx_wb_realization_user_nm_rrdt', 'user_id', 'nm_id', 'rr_dt'),
        Index('idx_wb_realization_brand', 'brand_name'),
        Index('idx_wb_realization_barcode', 'barcode'),
    )

    def __repr__(self):
        return (
            f"<WbRealizationReport("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"rr_dt={self.rr_dt}, "
            f"nm_id={self.nm_id}, "
            f"type={self.supplier_oper_name}, "
            f"amount={self.retail_amount}"
            f")>"
        )
