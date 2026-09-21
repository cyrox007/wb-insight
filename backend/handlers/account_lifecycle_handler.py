import hashlib
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from core.logger import setup_logger
from core.middleware import auth_middle
from core.session_cookie import clear_refresh_cookie
from models.mail_delivery import EmailVerificationToken, MailMessage, MailStatus
from models.users_model import User
from services.account_lifecycle_service import (
    deactivate_account,
    record_lifecycle_event,
    request_subscription_cancellation,
    reset_password,
    withdraw_subscription_cancellation,
)
from services.mail_service import queue_transactional_email
from services.mail_transport_service import get_mail_transport_runtime
from services.user_service import get_user_by_email, get_user_by_uuid
from settings import config
from utils.responce_helps import response_error, response_success


auth_router = APIRouter(prefix="/auth", tags=["authentication"])
account_router = APIRouter(prefix="/account", tags=["account lifecycle"])
logger = setup_logger(__name__)

lifecycle_config.validate(production=config.IS_PRODUCTION)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def _valid_email(value: str) -> bool:
    return bool(value and len(value) <= 254 and _EMAIL_RE.fullmatch(value))


@auth_router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "auth.password_reset.request"
    if not lifecycle_config.PASSWORD_RESET_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(code="PASSWORD_RECOVERY_NOT_CONFIGURED", message="Восстановление доступа временно недоступно")

    runtime = await get_mail_transport_runtime(db_session)
    if not runtime.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="PASSWORD_RECOVERY_DELIVERY_UNAVAILABLE",
            message="Восстановление доступа временно недоступно",
        )

    body = await request.json()
    email = _normalize_email(body.get("email"))
    if not _valid_email(email):
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
        # Keep recovery anti-enumeration while preventing a public endpoint from
        # becoming an inbox-spam amplifier. The response is intentionally
        # identical whether the account exists, is ineligible, or is throttled.
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=lifecycle_config.PASSWORD_RESET_RESEND_SECONDS
        )
        recent = await db_session.execute(
            select(MailMessage.id)
            .where(
                MailMessage.user_id == user.id,
                MailMessage.template_code == "password_reset",
                MailMessage.created_at >= cutoff,
            )
            .limit(1)
        )
        if recent.scalar_one_or_none() is None:
            bucket = int(
                datetime.now(timezone.utc).timestamp()
                // lifecycle_config.PASSWORD_RESET_RESEND_SECONDS
            )
            # The worker creates the one-time reset token only immediately before
            # provider delivery. Raw reset secrets therefore never live in the
            # durable mail queue or audit trail.
            await queue_transactional_email(
                db_session,
                user=user,
                template_code="password_reset",
                idempotency_key=f"password-reset:{user.id}:{bucket}",
            )

    return response_success(message="Если активный аккаунт с таким email существует, письмо отправлено")


@auth_router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "auth.password_reset.confirm"
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


@account_router.post("/email/change-request", dependencies=[Depends(auth_middle)])
async def request_email_change(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Stage a new login email and prove ownership before changing identity."""
    request.state.audit_action = "account.email_change.request"
    if not lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="EMAIL_VERIFICATION_NOT_CONFIGURED",
            message="Смена email временно недоступна",
        )

    runtime = await get_mail_transport_runtime(db_session)
    if not runtime.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="EMAIL_VERIFICATION_DELIVERY_UNAVAILABLE",
            message="Смена email временно недоступна: почтовый шлюз не готов",
        )

    user_id = UUID(str(request.state.user["sub"]))
    user = await get_user_by_uuid(db_session, user_id)
    if user is None or not user.is_active:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="USER_NOT_FOUND", message="Пользователь не найден")

    body = await request.json()
    target = _normalize_email(body.get("email"))
    if not _valid_email(target):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Укажите корректный email")
    if target == _normalize_email(user.email):
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="EMAIL_UNCHANGED", message="Этот email уже используется вашим аккаунтом")

    conflict_result = await db_session.execute(
        select(User.id)
        .where(User.id != user.id, func.lower(User.email) == target)
        .limit(1)
    )
    if conflict_result.scalar_one_or_none() is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="EMAIL_ALREADY_EXISTS", message="Этот email уже используется")

    previous_pending = _normalize_email(getattr(user, "pending_email", None))
    target_changed = previous_pending != target
    if target_changed:
        now = datetime.now(timezone.utc)
        user.pending_email = target

        # Immediately invalidate links/messages for an older staged address.
        await db_session.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db_session.execute(
            update(MailMessage)
            .where(
                MailMessage.user_id == user.id,
                MailMessage.template_code == "email_verification",
                MailMessage.status.in_([MailStatus.QUEUED.value, MailStatus.FAILED.value]),
            )
            .values(
                status=MailStatus.CANCELLED.value,
                safe_error_code="verification_target_replaced",
            )
        )
        await record_lifecycle_event(
            db_session,
            user_id=user.id,
            actor_user_id=user.id,
            event_type="email_change_requested",
            event_data={"target_changed": True},
        )

    bucket = int(
        datetime.now(timezone.utc).timestamp()
        // lifecycle_config.EMAIL_VERIFICATION_RESEND_SECONDS
    )
    target_digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
    await queue_transactional_email(
        db_session,
        user=user,
        template_code="email_verification",
        recipient_email=target,
        idempotency_key=f"email-change:{user.id}:{target_digest}:{bucket}",
    )
    await db_session.flush()

    return response_success(
        pending_email=target,
        message="Письмо подтверждения отправлено на новый адрес. Текущий email действует до подтверждения.",
    )


@account_router.delete("/email/change-request", dependencies=[Depends(auth_middle)])
async def cancel_email_change(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "account.email_change.cancel"
    user_id = UUID(str(request.state.user["sub"]))
    user = await get_user_by_uuid(db_session, user_id)
    if user is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="USER_NOT_FOUND", message="Пользователь не найден")
    if not getattr(user, "pending_email", None):
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="EMAIL_CHANGE_NOT_PENDING", message="Нет email, ожидающего подтверждения")

    now = datetime.now(timezone.utc)
    user.pending_email = None
    await db_session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db_session.execute(
        update(MailMessage)
        .where(
            MailMessage.user_id == user.id,
            MailMessage.template_code == "email_verification",
            MailMessage.status.in_([MailStatus.QUEUED.value, MailStatus.FAILED.value]),
        )
        .values(status=MailStatus.CANCELLED.value, safe_error_code="email_change_cancelled")
    )
    await record_lifecycle_event(
        db_session,
        user_id=user.id,
        actor_user_id=user.id,
        event_type="email_change_cancelled",
    )
    return response_success(message="Смена email отменена")


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
