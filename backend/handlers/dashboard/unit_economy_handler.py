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
from services.dashboard.financial_semantics import (
    FinancialMetricsResult,
    calculate_financial_metrics_scoped,
)
from services.dashboard.semantic_metrics import is_auth_sync_error
from services.user_sync_state_service import get_user_sync_states
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/unity", tags=["Юнит-экономика"])


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

    financial = await calculate_financial_metrics_scoped(
        db_session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    if financial.metrics.empty:
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

    return _format_response(
        financial.metrics,
        scope.selected_token_id,
        financial=financial,
    )


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
        "financial_adjustments": _clean_number(row.get("financial_adjustments")),
        "unallocated_wb_expenses": _clean_number(row.get("unallocated_wb_expenses")),
        "unallocated_financial_adjustments": _clean_number(
            row.get("unallocated_financial_adjustments")
        ),
    }


def _format_response(
    df: pd.DataFrame,
    selected_token_id: UUID | None = None,
    *,
    financial: FinancialMetricsResult | None = None,
) -> Dict[str, Any]:
    selected = str(selected_token_id) if selected_token_id is not None else None
    if df.empty:
        return response_success(data={}, selected_token_id=selected)

    summary = _serialize_table_row(df.iloc[0].to_dict())
    table = [
        _serialize_table_row(row)
        for row in df.iloc[1:].replace([np.nan], [None]).to_dict(orient="records")
    ]

    profit_complete = financial.profit_complete if financial else True
    cost_coverage_percent = financial.cost_coverage_percent if financial else 100.0
    cost_missing_operations = financial.cost_missing_operations if financial else 0
    summary_data = {
        "sales_with_spp": summary["sales_with_spp"],
        "sales_without_spp": summary["sales_without_spp"],
        "returns_amount": summary["returns_amount"],
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
        "financial_adjustments": summary["financial_adjustments"],
        "unallocated_wb_expenses": summary["unallocated_wb_expenses"],
        "unallocated_financial_adjustments": summary[
            "unallocated_financial_adjustments"
        ],
        "profit_complete": profit_complete,
        "cost_coverage_percent": cost_coverage_percent,
        "cost_missing_operations": cost_missing_operations,
        "profit_warning": (
            None
            if profit_complete
            else (
                "Прибыль неполная: для части операций отсутствует себестоимость "
                "на дату операции."
            )
        ),
    }
    return response_success(
        data={
            "summary": summary_data,
            "table": table,
            "daily_data": [],
        },
        selected_token_id=selected,
    )
