from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tokens_model import APIToken
from models.wb_finance_summary import WbFinanceBalanceCurrent, WbFinanceReportSummary
from models.wb_report import WbRealizationReport
from services.dashboard.account_scope import DashboardAccountScope


RECONCILIATION_TOLERANCE = Decimal("0.02")


def _money(value) -> float:
    return round(float(value or 0), 2)


def _delta(detail, summary) -> float:
    return round(float((detail or 0) - (summary or 0)), 2)


def _matched(delta: float) -> bool:
    return abs(Decimal(str(delta))) <= RECONCILIATION_TOLERANCE


async def get_finance_reconciliation(
    session: AsyncSession,
    *,
    user_id: UUID,
    scope: DashboardAccountScope,
    start_date: date,
    end_date: date,
) -> dict:
    report_query = (
        select(WbFinanceReportSummary)
        .where(
            WbFinanceReportSummary.user_id == user_id,
            WbFinanceReportSummary.date_to >= start_date,
            WbFinanceReportSummary.date_from <= end_date,
        )
        .order_by(
            WbFinanceReportSummary.date_from.desc(),
            WbFinanceReportSummary.report_id.desc(),
        )
    )
    report_query = scope.apply(report_query, WbFinanceReportSummary.token_id)
    reports = list((await session.execute(report_query)).scalars().all())

    token_query = select(APIToken.id, APIToken.label).where(
        APIToken.user_id == user_id,
        APIToken.id.in_(scope.token_ids),
    )
    token_rows = (await session.execute(token_query)).all()
    labels = {row.id: (row.label or "Wildberries") for row in token_rows}

    balance_query = select(WbFinanceBalanceCurrent).where(
        WbFinanceBalanceCurrent.user_id == user_id
    )
    balance_query = scope.apply(balance_query, WbFinanceBalanceCurrent.token_id)
    balances = list((await session.execute(balance_query)).scalars().all())

    report_ids_by_token: dict[UUID, set[int]] = defaultdict(set)
    for report in reports:
        report_ids_by_token[report.token_id].add(report.report_id)

    detail_by_key: dict[tuple[UUID, int], dict] = {}
    if reports:
        report_ids = sorted({report.report_id for report in reports})
        detail_query = (
            select(
                WbRealizationReport.token_id,
                WbRealizationReport.realization_report_id,
                func.count(WbRealizationReport.id).label("row_count"),
                func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("retail_amount"),
                func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("for_pay"),
                func.coalesce(func.sum(WbRealizationReport.delivery_rub), 0).label("delivery"),
                func.coalesce(func.sum(WbRealizationReport.storage_fee), 0).label("storage"),
                func.coalesce(func.sum(WbRealizationReport.acceptance), 0).label("acceptance"),
                func.coalesce(func.sum(WbRealizationReport.deduction), 0).label("deduction"),
                func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
                func.coalesce(func.sum(WbRealizationReport.additional_payment), 0).label("additional_payment"),
                func.coalesce(func.sum(WbRealizationReport.acquiring_fee), 0).label("acquiring_fee"),
            )
            .where(
                WbRealizationReport.user_id == user_id,
                WbRealizationReport.realization_report_id.in_(report_ids),
            )
            .group_by(
                WbRealizationReport.token_id,
                WbRealizationReport.realization_report_id,
            )
        )
        detail_query = scope.apply(detail_query, WbRealizationReport.token_id)
        for row in (await session.execute(detail_query)).all():
            if row.realization_report_id is None:
                continue
            key = (row.token_id, int(row.realization_report_id))
            # Same report IDs may exist in different accounts; additionally
            # ignore any accidental cross-account group not present in the
            # selected report set.
            if int(row.realization_report_id) not in report_ids_by_token.get(row.token_id, set()):
                continue
            detail_by_key[key] = {
                "row_count": int(row.row_count or 0),
                "retail_amount": row.retail_amount,
                "for_pay": row.for_pay,
                "delivery": row.delivery,
                "storage": row.storage,
                "acceptance": row.acceptance,
                "deduction": row.deduction,
                "penalty": row.penalty,
                "additional_payment": row.additional_payment,
                "acquiring_fee": row.acquiring_fee,
            }

    serialized_reports: list[dict] = []
    matched_count = 0
    mismatch_count = 0
    not_synced_count = 0

    for report in reports:
        detail = detail_by_key.get((report.token_id, report.report_id))
        if detail is None:
            status = "not_synced"
            not_synced_count += 1
            discrepancies = None
            detail_payload = None
        else:
            discrepancies = {
                "retail_amount": _delta(detail["retail_amount"], report.retail_amount_sum),
                "for_pay": _delta(detail["for_pay"], report.for_pay_sum),
                "delivery": _delta(detail["delivery"], report.delivery_service_sum),
                "storage": _delta(detail["storage"], report.paid_storage_sum),
                "acceptance": _delta(detail["acceptance"], report.paid_acceptance_sum),
                "deduction": _delta(detail["deduction"], report.deduction_sum),
                "penalty": _delta(detail["penalty"], report.penalty_sum),
                "additional_payment": _delta(
                    detail["additional_payment"], report.additional_payment_sum
                ),
            }
            status = (
                "matched"
                if all(_matched(value) for value in discrepancies.values())
                else "mismatch"
            )
            if status == "matched":
                matched_count += 1
            else:
                mismatch_count += 1
            detail_payload = {
                "row_count": detail["row_count"],
                "retail_amount": _money(detail["retail_amount"]),
                "for_pay": _money(detail["for_pay"]),
                "delivery": _money(detail["delivery"]),
                "storage": _money(detail["storage"]),
                "acceptance": _money(detail["acceptance"]),
                "deduction": _money(detail["deduction"]),
                "penalty": _money(detail["penalty"]),
                "additional_payment": _money(detail["additional_payment"]),
                "acquiring_fee": _money(detail["acquiring_fee"]),
            }

        serialized_reports.append(
            {
                "token_id": str(report.token_id),
                "account_label": labels.get(report.token_id, "Wildberries"),
                "report_id": report.report_id,
                "seller_finance_name": report.seller_finance_name,
                "date_from": report.date_from.isoformat(),
                "date_to": report.date_to.isoformat(),
                "create_date": report.create_date.isoformat() if report.create_date else None,
                "currency": report.currency,
                "report_type": report.report_type,
                "retail_amount": _money(report.retail_amount_sum),
                "for_pay": _money(report.for_pay_sum),
                "avg_sale_percent": round(float(report.avg_sale_percent or 0), 2),
                "delivery": _money(report.delivery_service_sum),
                "storage": _money(report.paid_storage_sum),
                "acceptance": _money(report.paid_acceptance_sum),
                "deduction": _money(report.deduction_sum),
                "penalty": _money(report.penalty_sum),
                "additional_payment": _money(report.additional_payment_sum),
                "cashback_amount": _money(report.cashback_amount_sum),
                "cashback_discount": _money(report.cashback_discount_sum),
                "cashback_commission_change": _money(report.cashback_commission_change_sum),
                "payment_schedule": _money(report.payment_schedule),
                "bank_payment": _money(report.bank_payment_sum),
                "bank_minus_for_pay": round(
                    _money(report.bank_payment_sum) - _money(report.for_pay_sum), 2
                ),
                "observed_at": report.observed_at.isoformat(),
                "reconciliation_status": status,
                "discrepancies": discrepancies,
                "detail": detail_payload,
            }
        )

    summary = {
        "report_count": len(reports),
        "retail_amount": round(sum(_money(r.retail_amount_sum) for r in reports), 2),
        "for_pay": round(sum(_money(r.for_pay_sum) for r in reports), 2),
        "delivery": round(sum(_money(r.delivery_service_sum) for r in reports), 2),
        "storage": round(sum(_money(r.paid_storage_sum) for r in reports), 2),
        "acceptance": round(sum(_money(r.paid_acceptance_sum) for r in reports), 2),
        "deduction": round(sum(_money(r.deduction_sum) for r in reports), 2),
        "penalty": round(sum(_money(r.penalty_sum) for r in reports), 2),
        "additional_payment": round(sum(_money(r.additional_payment_sum) for r in reports), 2),
        "bank_payment": round(sum(_money(r.bank_payment_sum) for r in reports), 2),
        "matched_reports": matched_count,
        "mismatch_reports": mismatch_count,
        "not_synced_reports": not_synced_count,
    }

    balance_rows = [
        {
            "token_id": str(row.token_id),
            "account_label": labels.get(row.token_id, "Wildberries"),
            "currency": row.currency,
            "current": _money(row.current_amount),
            "for_withdraw": _money(row.for_withdraw),
            "observed_at": row.observed_at.isoformat(),
        }
        for row in balances
    ]
    currencies = {row["currency"] for row in balance_rows if row["currency"]}
    if len(currencies) <= 1:
        summary["balance_current"] = round(sum(row["current"] for row in balance_rows), 2)
        summary["for_withdraw"] = round(sum(row["for_withdraw"] for row in balance_rows), 2)
        summary["balance_currency"] = next(iter(currencies), None)
    else:
        summary["balance_current"] = None
        summary["for_withdraw"] = None
        summary["balance_currency"] = None

    return {
        "summary": summary,
        "balances": balance_rows,
        "reports": serialized_reports,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
