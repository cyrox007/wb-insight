from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.token_services import insert_token
from utils.responce_helps import response_error, response_success

router = APIRouter(prefix='/dashboard', tags=['Tokens'])

@router.post('/tokens', dependencies=[Depends(auth_middle)])
async def create_token(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session)
):
    data = await request.json()

    user_id = UUID(request.state.user['sub'])

    if not user_id:
        return response_error(
            code="AUTH_ERROR",
            message="Не удалось определить пользователя"
        )
    raw_token = data.get("token")
    label = data.get("label")

    if not raw_token:
        return response_error(
            code="VALIDATION_ERROR",
            message="Токен обязателен"
        )

    token = await insert_token(
        session=db_session,
        user_id=user_id,
        raw_token=raw_token,
        label=label or "Токен"
    )

    if not token:
        return response_error(
            code="TOKEN_CREATE_ERROR",
            message="Не удалось сохранить токен"
        )

    return response_success(
        message="Токен добавлен",
        data={
            "id": str(token.id),
            "label": token.label
        }
    )