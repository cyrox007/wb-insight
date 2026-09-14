from fastapi import HTTPException, Request, status

from core.logger import setup_logger
from utils.jwt import verify_token


logger = setup_logger(__name__)


async def auth_middle(request: Request):
    """Validate a Bearer access token and expose its payload on request.state."""
    authorization = request.headers.get("authorization", "")
    scheme, separator, token_value = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token_value.strip():
        logger.warning("Отсутствует или некорректен Bearer-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "missing_or_invalid_token"},
        )

    user_data = verify_token(token_value.strip())
    if not user_data or not user_data.get("sub"):
        logger.warning("Недопустимый access-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token"},
        )

    # Refresh tokens must never be accepted as API access credentials.
    if user_data.get("type") == "refresh":
        logger.warning("Refresh-токен использован как access-токен")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token_type"},
        )

    request.state.user = user_data
