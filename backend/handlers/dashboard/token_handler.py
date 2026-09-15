from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from integrations.wildberries.token_metadata import WBTokenValidationError
from services.marketplace_access_service import get_wb_account_quota
from services.token_services import insert_token
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard", tags=["Tokens"])


@router.post("/tokens", dependencies=[Depends(auth_middle)])
async def create_token(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = UUID(str(request.state.user["sub"]))
    quota = await get_wb_account_quota(db_session, user_id)
    if not quota["allowed"]:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code=quota["code"] or "TOKEN_LIMIT_EXCEEDED",
            message="Достигнут лимит кабинетов Wildberries для текущего тарифа",
            limit=quota["limit"],
            used=quota["used"],
        )

    data = await request.json()
    raw_token = str(data.get("token") or "").strip()
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Токен обязателен",
        )

    try:
        token = await insert_token(
            session=db_session,
            user_id=user_id,
            raw_token=raw_token,
            label=data.get("label") or "Wildberries",
        )
    except WBTokenValidationError as exc:
        response.status_code = exc.status_code
        return response_error(
            code=exc.code,
            message=str(exc),
        )

    if not token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TOKEN_CREATE_ERROR",
            message="Не удалось сохранить токен",
        )

    return response_success(
        message="Токен добавлен",
        data={
            "id": str(token.id),
            "label": token.label,
            "marketplace": token.marketplace.value,
            "token_type": token.token_type,
            "external_account_id": token.external_account_id,
            "issued_at": token.issued_at,
            "expires_at": token.expires_at,
        },
    )
