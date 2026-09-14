from fastapi import APIRouter, Response

from settings import config
from utils.responce_helps import response_success


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(
        key=config.REFRESH_COOKIE_NAME,
        path="/auth/refresh",
        domain=config.COOKIE_DOMAIN,
        secure=config.COOKIE_SECURE,
        httponly=True,
        samesite=config.COOKIE_SAMESITE,
    )
    return response_success(message="Сессия завершена")
