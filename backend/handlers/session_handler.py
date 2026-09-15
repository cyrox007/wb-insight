from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.session_cookie import clear_refresh_cookie, set_refresh_cookie
from services.session_identity import session_user_payload
from services.user_service import get_user_by_uuid
from settings import config
from utils.jwt import create_access_token, create_refresh_token, verify_token
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    token = request.cookies.get(config.REFRESH_COOKIE_NAME)
    payload = verify_token(token) if token else None

    if not payload or payload.get("type") != "refresh" or not payload.get("sub"):
        clear_refresh_cookie(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="INVALID_TOKEN",
            message="Неверный refresh-токен",
        )

    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError):
        clear_refresh_cookie(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="INVALID_TOKEN",
            message="Неверный refresh-токен",
        )

    user = await get_user_by_uuid(db_session, user_id)
    if not user or not user.is_active:
        clear_refresh_cookie(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="SESSION_REVOKED",
            message="Сессия недействительна",
        )

    token_data = {
        "sub": str(user.id),
        "email": user.email,
    }
    access_token = create_access_token(token_data)
    set_refresh_cookie(response, create_refresh_token(token_data))

    return response_success(
        access_token=access_token,
        token_type="bearer",
        expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=session_user_payload(user),
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_refresh_cookie(response)
    return response_success(message="Сессия завершена")
