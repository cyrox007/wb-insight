from fastapi import HTTPException, Request, status
from core.logger import setup_logger
from utils.jwt import verify_token


logger = setup_logger(__name__)

async def auth_middle(request: Request):
    # Получаем заголовок Authorization
    token = request.headers.get("authorization")
    if not token:
        logger.warning("Отсутствующий токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "missing_token"}
        )

    # Логируем полученный токен
    logger.info(f"Полученный токен из заголовков: {token.split(' ')[1][:10]}...")

    # Валидируем токен
    scheme, _, token_value = token.partition(" ")
    user_data = verify_token(token_value)
    if not user_data:
        logger.warning("Недопустимый токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_token"}
        )

    # Сохраняем данные пользователя в request.state для дальнейшего использования
    request.state.user = user_data
    # logger.info(f"Аутентифицированный пользователь: {user_data}")