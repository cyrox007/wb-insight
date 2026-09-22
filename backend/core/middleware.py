from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from core.database import Database
from core.logger import setup_logger
from models.users_model import User
from settings import config
from utils.jwt import verify_token


logger = setup_logger(__name__)


async def _load_account_state(user_id: UUID) -> tuple[bool, int] | None:
    async with Database.sessionmaker()() as session:
        result = await session.execute(
            select(User.is_active, User.session_version).where(User.id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return bool(row.is_active), int(row.session_version)


async def auth_middle(request: Request):
    """Проверяет Bearer access-токен и версию активной сессии аккаунта."""
    authorization = request.headers.get("authorization", "")
    scheme, separator, token_value = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token_value.strip():
        logger.warning("Отсутствует или некорректен Bearer-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "missing_or_invalid_token"},
        )

    user_data = verify_token(token_value.strip())
    if (
        not user_data
        or not user_data.get("sub")
        or user_data.get("type") != "access"
    ):
        logger.warning("Недопустимый access-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_access_token"},
        )

    session_version = user_data.get("sv")
    if session_version is None and not config.IS_PRODUCTION:
        # Совместимость только для тестов разработки и старых локальных токенов.
        # В рабочем окружении привязка к версии сессии обязательна.
        request.state.user = user_data
        return

    try:
        user_id = UUID(str(user_data["sub"]))
        token_session_version = int(session_version)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_access_token"},
        )

    account_state = await _load_account_state(user_id)
    if (
        account_state is None
        or not account_state[0]
        or account_state[1] != token_session_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "session_revoked"},
        )

    request.state.user = user_data
