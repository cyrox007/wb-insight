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
    resolve_dashboard_token_id,
)
from services.dashboard.semantic_metrics import is_auth_sync_error
from services.dashboard.unit_economy_service import UnitEconomyMetricsService
from services.dashboard.unit_report_scope import get_reports_with_costs_scoped
from services.marketplace_access_service import get_allowed_wb_tokens
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
        token_id = await resolve_dashboard_token_id(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(code="ACCOUNT_NOT_AVAILABLE", message=str(exc))

    states = await get_user_sync_states(session=db_session, user_id=user_id)
    scoped_states = [
        state for state in states if token_id is None or state.token_id == token_id
    ]
    sync_errors = [state.last_error for state in scoped_states if state.last_error]
    allowed_tokens = await get_allowed_wb_tokens(db_session, user_id)

    if not allowed_tokens and token_id is None:
        if any(is_auth_sync_error(error) for error in sync_errors):
            return response_error(
                message=(
                    "Ошибка авторизации: подключение недействительно или истекло. "
                    "Пожалуйста, обновите кабинет Wildberries в настройках."
                ),
                code="TOKEN_INVALID",
            )
        return response_error(
            message=(
                "Нет действительных токенов для синхронизации. "
                "Пожалуйста, добавьте актуальный токен Wildberries."
            ),
            code="NO_VALID_TOKENS",
        )

    reports_with_costs = await get_reports_with_costs_scoped(
        db_session,
        user_id,
        start_date,
        end_date,
        token_id,
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

    tax_rate = await get_user_tax_rate(db_session, user_id)
    metrics_service = UnitEconomyMetricsService(tax_rate=tax_rate)
    result_df = metrics_service.calculate_all_metrics(pd.DataFrame(report_data))
    response = _format_response(result_df)
    if isinstance(response, dict):
        response["selected_token_id"] = str(token_id) if token_id else None
    return response


def _format_response(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df) == 0:
        return response_success(data={})

    summary_row = df.iloc[0].to_dict()
    articles_df = df.iloc[1:].copy()
    table_data = articles_df.replace([np.nan], [None]).to_dict(orient="records")

    summary_data = {
        "sales_with_spp": summary_row.get("sales_with_spp", 0),
        "wb_commission_percent": summary_row.get("wb_commission_percent", 0),
        "wb_commission_amount": (
            summary_row.get("sales_with_spp", 0)
            * summary_row.get("wb_commission_percent", 0)
            / 100
        ),
        "to_pay_seller": summary_row.get("to_pay_seller", 0),
        "logistics": summary_row.get("logistics_total", 0),
        "storage": summary_row.get("storage", 0),
        "other_deductions": summary_row.get("other_deductions", 0),
        "fines": summary_row.get("fines", 0),
        "paid_acceptance": summary_row.get("paid_acceptance", 0),
        "total_to_pay": summary_row.get("total_to_pay", 0),
        "avg_sale_price": summary_row.get("avg_sale_price", 0),
        "tax": summary_row.get("tax", 0),
        "other_expenses": 0,
        "drr": summary_row.get("drr", 0),
        "cost_price": summary_row.get("cost_price_total", 0),
        "marginality": summary_row.get("margin", 0),
        "profitability": summary_row.get("profitability", 0),
        "profit_per_unit": summary_row.get("profit_per_unit", 0),
        "profit": summary_row.get("profit", 0),
    }
    return response_success(
        data={
            "summary": summary_data,
            "table": table_data,
            "daily_data": [],
        },
        selected_token_id=None,
    )
