from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from core.operation_context import get_operation_context
from services.dashboard.account_scope import DashboardAccountScope
from services.dashboard.semantic_metrics import get_advertising_spend_by_nm
from services.dashboard.unit_economy_metrics import UnitEconomyMetricsService
from services.dashboard.unit_report_scope import get_reports_with_costs_scoped
from services.manual_expense_service import get_manual_expense_totals
from services.operation_log_service import persist_current_operation_event
from services.user_service import get_user_tax_rate


_COST_RELEVANT_OPERATIONS = {
    "Продажа",
    "Возврат",
    "Коррекция продаж",
    "Коррекция возвратов",
}


@dataclass(frozen=True)
class FinancialMetricsResult:
    metrics: pd.DataFrame
    profit_complete: bool
    cost_coverage_percent: float
    cost_missing_operations: int
    products_with_cost: int
    products_without_cost: int


def _report_row(report, cost) -> dict:
    return {
        "nm_id": report.nm_id,
        "supplier_oper_name": report.supplier_oper_name,
        "doc_type_name": report.doc_type_name,
        "quantity": report.quantity,
        "retail_price_with_disc_rub": report.retail_price_with_disc_rub,
        "retail_amount": report.retail_amount,
        "delivery_amount": report.delivery_amount,
        "return_amount": report.return_amount,
        "ppvz_kvw_prc_base": report.ppvz_kvw_prc_base,
        "ppvz_sales_commission": report.ppvz_sales_commission,
        "ppvz_for_pay": report.ppvz_for_pay,
        "delivery_rub": report.delivery_rub,
        "return_rub": report.return_rub,
        "rebill_logistic_cost": report.rebill_logistic_cost,
        "acquiring_fee": report.acquiring_fee,
        "storage_fee": report.storage_fee,
        "penalty": report.penalty,
        "deduction": report.deduction,
        "acceptance": report.acceptance,
        "additional_payment": report.additional_payment,
        "ppvz_vw_nds": report.ppvz_vw_nds,
        "product_cost": cost.cost_price if cost else 0,
        "cost_known": cost is not None,
    }


def reports_to_financial_frame(reports_with_costs: list[tuple]) -> pd.DataFrame:
    """Преобразует строки Finance API в единый вход для расчёта показателей."""
    return pd.DataFrame(
        [_report_row(report, cost) for report, cost in reports_with_costs]
    )


def _cost_coverage(frame: pd.DataFrame) -> tuple[bool, float, int, int, int]:
    if frame.empty:
        return True, 100.0, 0, 0, 0

    operation = frame["supplier_oper_name"].fillna("")
    quantity = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0).abs()
    relevant = operation.isin(_COST_RELEVANT_OPERATIONS) & (quantity > 0)
    relevant_frame = frame.loc[relevant, ["nm_id", "cost_known"]].copy()
    if relevant_frame.empty:
        return True, 100.0, 0, 0, 0

    relevant_frame["cost_known"] = relevant_frame["cost_known"].fillna(False).astype(bool)
    missing_operations = int((~relevant_frame["cost_known"]).sum())
    total_operations = int(len(relevant_frame))
    coverage_percent = (total_operations - missing_operations) / total_operations * 100

    product_coverage = relevant_frame.groupby("nm_id")["cost_known"].all()
    products_with_cost = int(product_coverage.sum())
    products_without_cost = int((~product_coverage).sum())
    return (
        missing_operations == 0,
        round(coverage_percent, 2),
        missing_operations,
        products_with_cost,
        products_without_cost,
    )


def _plain_value(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _metrics_summary(metrics: pd.DataFrame) -> dict[str, Any]:
    if metrics.empty:
        return {}
    return {
        str(key): _plain_value(value)
        for key, value in metrics.iloc[0].to_dict().items()
    }


async def _trace_calculation(
    step: str,
    status: str,
    *,
    user_id: UUID,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        domain="calculation",
        operation="financial_metrics",
        step=step,
        status=status,
        event_kind="calculation_step",
        component="financial_semantics",
        direction="internal",
        user_id=user_id,
        subject_type="user",
        subject_id=user_id,
        message=f"Шаг финансового расчёта: {step}",
        input_data=input_data or {},
        output_data=output_data or {},
        metrics=metrics or {},
    )


async def calculate_financial_metrics_scoped(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> FinancialMetricsResult:
    """Считает финансовые показатели единообразно для всех экранов аналитики."""
    token_ids = [str(item) for item in scope.token_ids]
    await _trace_calculation(
        "calculation_started",
        "started",
        user_id=user_id,
        input_data={
            "period_from": start_date,
            "period_to": end_date,
            "token_ids": token_ids,
            "selected_token_id": scope.selected_token_id,
        },
    )

    reports_with_costs = await get_reports_with_costs_scoped(
        session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    frame = reports_to_financial_frame(reports_with_costs)
    await _trace_calculation(
        "finance_rows_loaded",
        "success",
        user_id=user_id,
        output_data={
            "rows": len(reports_with_costs),
            "products": int(frame["nm_id"].nunique()) if not frame.empty else 0,
        },
    )
    if frame.empty:
        await _trace_calculation(
            "calculation_completed",
            "success",
            user_id=user_id,
            output_data={
                "result": "empty",
                "profit_complete": True,
                "cost_coverage_percent": 100.0,
            },
        )
        return FinancialMetricsResult(
            metrics=pd.DataFrame(),
            profit_complete=True,
            cost_coverage_percent=100.0,
            cost_missing_operations=0,
            products_with_cost=0,
            products_without_cost=0,
        )

    (
        profit_complete,
        cost_coverage_percent,
        cost_missing_operations,
        products_with_cost,
        products_without_cost,
    ) = _cost_coverage(frame)
    await _trace_calculation(
        "cost_coverage_calculated",
        "success" if profit_complete else "warning",
        user_id=user_id,
        output_data={
            "profit_complete": profit_complete,
            "cost_coverage_percent": cost_coverage_percent,
            "cost_missing_operations": cost_missing_operations,
            "products_with_cost": products_with_cost,
            "products_without_cost": products_without_cost,
        },
    )

    advertising_costs_map = await get_advertising_spend_by_nm(
        session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    manual_expenses_total, manual_expenses_map = await get_manual_expense_totals(
        session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    tax_rate = await get_user_tax_rate(session, user_id)
    await _trace_calculation(
        "additional_costs_loaded",
        "success",
        user_id=user_id,
        output_data={
            "advertising_products": len(advertising_costs_map),
            "manual_expense_products": len(manual_expenses_map),
            "manual_expenses_total": manual_expenses_total,
            "tax_rate": tax_rate,
        },
    )

    service = UnitEconomyMetricsService(tax_rate=tax_rate)
    metrics = service.calculate_all_metrics(
        frame,
        advertising_costs_map=advertising_costs_map,
        manual_expenses_map=manual_expenses_map,
        manual_expenses_total=manual_expenses_total,
    )
    await _trace_calculation(
        "calculation_completed",
        "success" if profit_complete else "warning",
        user_id=user_id,
        output_data={
            "rows": len(metrics.index),
            "summary": _metrics_summary(metrics),
            "profit_complete": profit_complete,
            "cost_coverage_percent": cost_coverage_percent,
        },
    )
    return FinancialMetricsResult(
        metrics=metrics,
        profit_complete=profit_complete,
        cost_coverage_percent=cost_coverage_percent,
        cost_missing_operations=cost_missing_operations,
        products_with_cost=products_with_cost,
        products_without_cost=products_without_cost,
    )