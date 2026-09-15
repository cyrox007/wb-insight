from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.dashboard.account_scope import (
    DashboardAccountUnavailableError,
    resolve_dashboard_scope,
)
from services.dashboard.inventory_replenishment import get_inventory_replenishment
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/stocks", tags=["Inventory"])


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_inventory_dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    token_id: Optional[UUID] = None,
):
    user_id = UUID(str(request.state.user["sub"]))
    try:
        scope = await resolve_dashboard_scope(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(code="ACCOUNT_NOT_AVAILABLE", message=str(exc))

    if not scope.token_ids:
        return response_error(
            code="NO_VALID_TOKENS",
            message="Нет действительных кабинетов Wildberries, доступных на текущем тарифе.",
        )

    data = await get_inventory_replenishment(
        db_session,
        user_id=user_id,
        scope=scope,
    )
    return response_success(
        data=data,
        selected_token_id=(
            str(scope.selected_token_id) if scope.selected_token_id else None
        ),
    )
