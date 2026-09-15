from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.dashboard.account_scope import (
    DashboardAccountUnavailableError,
    resolve_dashboard_scope,
)
from services.dashboard.finance_reconciliation import get_finance_reconciliation
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/finance", tags=["Finance"])


@router.get("/", dependencies=[Depends(auth_middle)])
async def finance_reconciliation(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: date | None = None,
    end_date: date | None = None,
    token_id: UUID | None = None,
):
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=89))
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    try:
        scope = await resolve_dashboard_scope(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(message=str(exc), code="ACCOUNT_NOT_AVAILABLE")

    data = await get_finance_reconciliation(
        db_session,
        user_id=user_id,
        scope=scope,
        start_date=start_date,
        end_date=end_date,
    )
    return response_success(data=data, selected_token_id=str(scope.selected_token_id) if scope.selected_token_id else None)
