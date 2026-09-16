from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from core.logger import setup_logger
from core.middleware import auth_middle
from core.session_cookie import clear_refresh_cookie
from services.account_lifecycle_service import (
    deactivate_account,
    request_subscription_cancellation,
    reset_password,
    withdraw_subscription_cancellation,
)
from services.mail_service import queue_transactional_email
from services.user_service import get_user_by_email, get_user_by_uuid
from settings import config
from utils.responce_helps import response_error, response_success


auth_router = APIRouter(prefix="/auth", tags=["authentication"])
account_router = APIRouter(prefix="/account", tags=["account lifecycle"])
logger = setup_logger(__name__)

lifecycle_config.validate(production=config.IS_PRODUCTION)


@auth_router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not lifecycle_config.PASSWORD_RESET_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(code="PASSWORD_RECOVERY_NOT_CONFIGURED", message="Восстановление доступа временно недоступно")

    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    if not email or len(email) > 254:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Укажите корректный email")

    user = await get_user_by_email(db_session, email)
    verified_for_recovery = (
        user is not None
        and user.is_active
        and (
            not lifecycle_config.EMAIL_VERIFICATION_ENABLED
            or getattr(user, "email_verified_at", None) is not None
        )
    )
    if verified_for_recovery:
        # The worker creates the one-time reset token only immediately before SMTP
        # delivery. Raw reset secrets therefore never live in the durable mail queue.
        await queue_transactional_email(
            db_session,
            user=user,
            template_code="password_reset",
        )

    return response_success(message="Если активный аккаунт с таким email существует, письмо отправлено")


@auth_router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    body = await request.json()
    raw_token = str(body.get("token") or "").strip()
    new_password = str(body.get("new_password") or "")
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Не указан reset token")
    try:
        user = await reset_password(db_session, raw_token=raw_token, new_password=new_password)
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message=str(exc))
    if user is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="RESET_TOKEN_INVALID", message="Ссылка восстановления недействительна или истекла")
    clear_refresh_cookie(response)
    return response_success(message="Пароль изменён. Войдите заново на всех устройствах")


@account_router.post("/deactivate", dependencies=[Depends(auth_middle)])
async def deactivate_current_account(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_id = UUID(str(request.state.user["sub"]))
    user = await get_user_by_uuid(db_session, user_id)
    if user is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="USER_NOT_FOUND", message="Пользователь не найден")
    body = await request.json()
    reason = str(body.get("reason") or "").strip() or None
    changed = await deactivate_account(db_session, user, actor_user_id=user_id, reason=reason)
    if not changed:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="ACCOUNT_ALREADY_INACTIVE", message="Аккаунт уже деактивирован")
    clear_refresh_cookie(response)
    return response_success(
        deactivated=True,
        retention_until=user.retention_until.isoformat() if user.retention_until else None,
        message="Аккаунт деактивирован; данные не удаляются немедленно",
    )


@account_router.post("/subscription/cancel", dependencies=[Depends(auth_middle)])
async def cancel_current_subscription(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_id = UUID(str(request.state.user["sub"]))
    body = await request.json()
    subscription = await request_subscription_cancellation(
        db_session, user_id=user_id, reason=str(body.get("reason") or "").strip() or None
    )
    if subscription is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="ACTIVE_SUBSCRIPTION_NOT_FOUND", message="Активная подписка не найдена")
    return response_success(
        subscription_id=str(subscription.id),
        cancel_at_period_end=True,
        access_until=subscription.current_period_end.isoformat(),
        message="Автопродление отключено; доступ сохранён до конца оплаченного периода",
    )


@account_router.delete("/subscription/cancel", dependencies=[Depends(auth_middle)])
async def undo_current_subscription_cancellation(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_id = UUID(str(request.state.user["sub"]))
    subscription = await withdraw_subscription_cancellation(db_session, user_id=user_id)
    if subscription is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="CANCELLATION_NOT_FOUND", message="Активная заявка на отмену не найдена")
    return response_success(
        subscription_id=str(subscription.id),
        cancel_at_period_end=False,
        message="Отмена подписки отозвана",
    )
