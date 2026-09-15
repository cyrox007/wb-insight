from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_finance_summary import WbFinanceBalanceCurrent, WbFinanceReportSummary


MONEY_FIELDS = {
    "retail_amount_sum": "retailAmountSum",
    "for_pay_sum": "forPaySum",
    "delivery_service_sum": "deliveryServiceSum",
    "paid_storage_sum": "paidStorageSum",
    "paid_acceptance_sum": "paidAcceptanceSum",
    "deduction_sum": "deductionSum",
    "penalty_sum": "penaltySum",
    "additional_payment_sum": "additionalPaymentSum",
    "cashback_amount_sum": "cashbackAmountSum",
    "cashback_discount_sum": "cashbackDiscountSum",
    "cashback_commission_change_sum": "cashbackCommissionChangeSum",
    "payment_schedule": "paymentSchedule",
    "bank_payment_sum": "bankPaymentSum",
}


def money(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Некорректное денежное значение WB: {value!r}") from exc


def report_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"Некорректная дата финансового отчёта WB: {value!r}") from exc


def normalize_finance_report_summary(
    item: dict[str, Any],
    *,
    user_id: UUID,
    token_id: UUID,
    observed_at: datetime,
) -> dict[str, Any]:
    report_id = item.get("reportId")
    date_from = report_date(item.get("dateFrom"))
    date_to = report_date(item.get("dateTo"))
    if report_id in (None, "") or date_from is None or date_to is None:
        raise ValueError("WB finance report summary is missing identity fields")

    row: dict[str, Any] = {
        "user_id": user_id,
        "token_id": token_id,
        "report_id": int(report_id),
        "seller_finance_name": item.get("sellerFinanceName"),
        "date_from": date_from,
        "date_to": date_to,
        "create_date": report_date(item.get("createDate")),
        "currency": item.get("currency"),
        "report_type": int(item["reportType"]) if item.get("reportType") is not None else None,
        "avg_sale_percent": money(item.get("avgSalePercent")),
        "observed_at": observed_at,
    }
    for target, source in MONEY_FIELDS.items():
        row[target] = money(item.get(source))
    return row


async def save_finance_report_summaries(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    items: list[dict[str, Any]],
    observed_at: datetime,
) -> int:
    rows = [
        normalize_finance_report_summary(
            item,
            user_id=user_id,
            token_id=token_id,
            observed_at=observed_at,
        )
        for item in items
    ]
    if not rows:
        return 0

    stmt = insert(WbFinanceReportSummary).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_wb_finance_report_account_report",
        set_={
            "seller_finance_name": excluded.seller_finance_name,
            "date_from": excluded.date_from,
            "date_to": excluded.date_to,
            "create_date": excluded.create_date,
            "currency": excluded.currency,
            "report_type": excluded.report_type,
            "retail_amount_sum": excluded.retail_amount_sum,
            "for_pay_sum": excluded.for_pay_sum,
            "avg_sale_percent": excluded.avg_sale_percent,
            "delivery_service_sum": excluded.delivery_service_sum,
            "paid_storage_sum": excluded.paid_storage_sum,
            "paid_acceptance_sum": excluded.paid_acceptance_sum,
            "deduction_sum": excluded.deduction_sum,
            "penalty_sum": excluded.penalty_sum,
            "additional_payment_sum": excluded.additional_payment_sum,
            "cashback_amount_sum": excluded.cashback_amount_sum,
            "cashback_discount_sum": excluded.cashback_discount_sum,
            "cashback_commission_change_sum": excluded.cashback_commission_change_sum,
            "payment_schedule": excluded.payment_schedule,
            "bank_payment_sum": excluded.bank_payment_sum,
            "observed_at": excluded.observed_at,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return len(rows)


async def save_finance_balance(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    payload: dict[str, Any],
    observed_at: datetime | None = None,
) -> None:
    captured_at = observed_at or datetime.now(timezone.utc)
    row = {
        "user_id": user_id,
        "token_id": token_id,
        "currency": payload.get("currency"),
        "current_amount": money(payload.get("current")),
        "for_withdraw": money(payload.get("for_withdraw")),
        "observed_at": captured_at,
    }
    stmt = insert(WbFinanceBalanceCurrent).values(row)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_wb_finance_balance_account",
        set_={
            "user_id": excluded.user_id,
            "currency": excluded.currency,
            "current_amount": excluded.current_amount,
            "for_withdraw": excluded.for_withdraw,
            "observed_at": excluded.observed_at,
        },
    )
    await session.execute(stmt)
    await session.flush()
