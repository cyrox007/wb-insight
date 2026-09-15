from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.dashboard.account_scope import (
    DashboardAccountUnavailableError,
    resolve_dashboard_scope,
)
from services.dashboard.semantic_metrics import (
    get_advertising_spend_by_nm,
    is_auth_sync_error,
)
from services.dashboard.unit_economy_metrics import UnitEconomyMetricsService
from services.dashboard.unit_report_scope import get_reports_with_costs_scoped
from services.manual_expense_service import get_manual_expense_totals
from services.user_service import get_user_tax_rate
from services.user_sync_state_service import get_user_sync_states
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/unity", tags=["Unit"])


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_unit_economy(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    token_id: Optional[UUID] = None,
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    try:
        scope = await resolve_dashboard_scope(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(code="ACCOUNT_NOT_AVAILABLE", message=str(exc))

    states = await get_user_sync_states(session=db_session, user_id=user_id)
    scoped_states = [state for state in states if scope.contains(state.token_id)]
    sync_errors = [state.last_error for state in scoped_states if state.last_error]

    if not scope.token_ids:
        if any(is_auth_sync_error(error) for error in sync_errors):
            return response_error(
                message=(
                    "Ошибка авторизации: подключение недействительно или истекло. "
                    "Пожалуйста, обновите кабинет Wildberries в настройках."
                ),
                code="TOKEN_INVALID",
            )
        return response_error(
            message="Нет действительных кабинетов Wildberries, доступных на текущем тарифе.",
            code="NO_VALID_TOKENS",
        )

    reports_with_costs = await get_reports_with_costs_scoped(
        db_session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    if not reports_with_costs:
        has_success = any(state.last_success_at is not None for state in scoped_states)
        if not has_success:
            return response_error(
                code="NOT_SYNCED",
                message=(
                    "Данные еще не синхронизированы. Проверьте статус кабинета "
                    "и дождитесь завершения синхронизации."
                ),
            )
        return response_error(
            code="NOT_DATA",
            message="Нет данных за выбранный период. Попробуйте изменить диапазон дат.",
        )

    report_data = []
    for report, cost in reports_with_costs:
        report_data.append(
            {
                "nm_id": report.nm_id,
                "supplier_oper_name": report.supplier_oper_name,
                "doc_type_name": report.doc_type_name,
                "quantity": report.quantity,
                "retail_price_with_disc_rub": report.retail_price_with_disc_rub,
                "retail_amount": report.retail_amount,
                "delivery_amount": report.delivery_amount,
                "ppvz_kvw_prc_base": report.ppvz_kvw_prc_base,
                "ppvz_sales_commission": report.ppvz_sales_commission,
                "ppvz_for_pay": report.ppvz_for_pay,
                "delivery_rub": report.delivery_rub,
                "acquiring_fee": report.acquiring_fee,
                "storage_fee": report.storage_fee,
                "penalty": report.penalty,
                "deduction": report.deduction,
                "acceptance": report.acceptance,
                "ppvz_vw_nds": report.ppvz_vw_nds,
                "product_cost": cost.cost_price if cost else 0,
            }
        )

    advertising_costs_map = await get_advertising_spend_by_nm(
        db_session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    manual_expenses_total, manual_expenses_map = await get_manual_expense_totals(
        db_session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    tax_rate = await get_user_tax_rate(db_session, user_id)
    metrics_service = UnitEconomyMetricsService(tax_rate=tax_rate)
    result_df = metrics_service.calculate_all_metrics(
        pd.DataFrame(report_data),
        advertising_costs_map=advertising_costs_map,
        manual_expenses_map=manual_expenses_map,
        manual_expenses_total=manual_expenses_total,
    )
    return _format_response(result_df, scope.selected_token_id)


def _clean_number(value: Any, default: float = 0.0):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.generic):
        return value.item()
    return value


def _serialize_table_row(row: dict[str, Any]) -> dict[str, Any]:
    nm_id = _clean_number(row.get("nm_id"), 0)
    payout = _clean_number(row.get("ppvz_for_pay"))
    return {
        "wb_article": int(nm_id) if nm_id else None,
        "sales_without_spp": _clean_number(row.get("sales_without_spp")),
        "sales_with_spp": _clean_number(row.get("sales_with_spp")),
        "returns_amount": _clean_number(row.get("returns_amount")),
        "sales_qty": _clean_number(row.get("sales_quantity")),
        "deliveries_qty": _clean_number(row.get("delivery_quantity")),
        "returns_qty": _clean_number(row.get("returns_quantity")),
        "buyout_percent": _clean_number(row.get("buyout_percent")),
        "acquiring": _clean_number(row.get("acquiring_fee")),
        "wb_commission_percent": _clean_number(row.get("ppvz_kvw_prc_base")),
        "wb_commission_amount": _clean_number(row.get("ppvz_sales_commission")),
        "to_pay_seller": payout,
        "logistics_total": _clean_number(row.get("delivery_rub")),
        "storage": _clean_number(row.get("storage_fee")),
        "fines": _clean_number(row.get("penalty")),
        "other_deductions": _clean_number(row.get("deduction")),
        "tax": _clean_number(row.get("tax")),
        "ad_expenses": _clean_number(row.get("advertising_cost")),
        "other_expenses": _clean_number(row.get("other_expenses")),
        "drr": _clean_number(row.get("drr")),
        "paid_acceptance": _clean_number(row.get("acceptance")),
        "total_to_pay": payout,
        "cost_price_total": _clean_number(row.get("product_cost")),
        "total_expenses": _clean_number(row.get("total_costs")),
        "profit": _clean_number(row.get("profit")),
        "profit_per_unit": _clean_number(row.get("profit_per_unit")),
        "margin": _clean_number(row.get("margin")),
        "profitability": _clean_number(row.get("roi")),
        "avg_sale_price": _clean_number(row.get("avg_selling_price")),
    }


def _format_response(
    df: pd.DataFrame,
    selected_token_id: UUID | None = None,
) -> Dict[str, Any]:
    selected = str(selected_token_id) if selected_token_id is not None else None
    if df.empty:
        return response_success(data={}, selected_token_id=selected)

    summary = _serialize_table_row(df.iloc[0].to_dict())
    table = [
        _serialize_table_row(row)
        for row in df.iloc[1:].replace([np.nan], [None]).to_dict(orient="records")
    ]

    summary_data = {
        "sales_with_spp": summary["sales_with_spp"],
        "wb_commission_percent": summary["wb_commission_percent"],
        "wb_commission_amount": summary["wb_commission_amount"],
        "to_pay_seller": summary["to_pay_seller"],
        "logistics": summary["logistics_total"],
        "storage": summary["storage"],
        "other_deductions": summary["other_deductions"],
        "fines": summary["fines"],
        "paid_acceptance": summary["paid_acceptance"],
        "total_to_pay": summary["total_to_pay"],
        "avg_sale_price": summary["avg_sale_price"],
        "tax": summary["tax"],
        "other_expenses": summary["other_expenses"],
        "drr": summary["drr"],
        "cost_price": summary["cost_price_total"],
        "marginality": summary["margin"],
        "profitability": summary["profitability"],
        "profit_per_unit": summary["profit_per_unit"],
        "profit": summary["profit"],
    }
    return response_success(
        data={
            "summary": summary_data,
            "table": table,
            "daily_data": [],
        },
        selected_token_id=selected,
    )
