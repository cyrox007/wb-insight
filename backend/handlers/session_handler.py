from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.session_cookie import clear_refresh_cookie, set_refresh_cookie
from models.users_model import User
from services.session_identity import session_user_payload
from services.user_service import get_user_by_uuid
from settings import config
from utils.jwt import create_access_token, create_refresh_token, verify_token
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/auth", tags=["Аутентификация"])


def _bearer_token(request: Request) -> str | None:
    authorization = str(request.headers.get("authorization") or "").strip()
    scheme, separator, token = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _logout_payload(request: Request) -> dict | None:
    refresh_token = request.cookies.get(config.REFRESH_COOKIE_NAME)
    candidates = (refresh_token, _bearer_token(request))
    for token in candidates:
        if not token:
            continue
        payload = verify_token(token)
        if payload and payload.get("type") in {"refresh", "access"}:
            return payload
    return None


async def _revoke_session_version(
    db_session: AsyncSession,
    payload: dict | None,
) -> bool:
    if not payload or not payload.get("sub"):
        return False
    try:
        user_id = UUID(str(payload["sub"]))
        token_session_version = int(payload.get("sv"))
    except (TypeError, ValueError):
        return False

    result = await db_session.execute(
        update(User)
        .where(
            User.id == user_id,
            User.session_version == token_session_version,
        )
        .values(session_version=User.session_version + 1)
    )
    return bool(result.rowcount)


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
        token_session_version = int(payload.get("sv"))
    except (TypeError, ValueError):
        clear_refresh_cookie(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="INVALID_TOKEN",
            message="Неверный refresh-токен",
        )

    user = await get_user_by_uuid(db_session, user_id)
    if (
        not user
        or not user.is_active
        or user.session_version != token_session_version
    ):
        clear_refresh_cookie(response)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="SESSION_REVOKED",
            message="Сессия недействительна",
        )

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "sv": user.session_version,
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
async def logout(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = _logout_payload(request)
    revoked = await _revoke_session_version(db_session, payload)
    clear_refresh_cookie(response)
    return response_success(
        message="Выход выполнен на всех устройствах",
        session_revoked=revoked,
    )
