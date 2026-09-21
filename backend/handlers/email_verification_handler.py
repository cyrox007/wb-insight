from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from core.session_cookie import clear_refresh_cookie
from models.mail_delivery import MailMessage
from services.email_verification_service import EmailVerificationTargetConflict, verify_email
from services.mail_service import queue_transactional_email
from services.mail_transport_service import get_mail_transport_runtime
from services.user_service import get_user_by_email
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/auth/email-verification", tags=["email verification"])


def _generic_resend_response() -> dict:
    return response_success(
        message="Если адрес зарегистрирован и ещё не подтверждён, письмо будет отправлено."
    )


@router.post("/confirm")
async def confirm_email(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "auth.email_verification.confirm"
    data = await request.json()
    raw_token = str(data.get("token") or "").strip()
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="EMAIL_VERIFICATION_TOKEN_REQUIRED", message="Отсутствует код подтверждения")

    try:
        user = await verify_email(db_session, raw_token)
    except EmailVerificationTargetConflict:
        await db_session.rollback()
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="EMAIL_ALREADY_EXISTS",
            message="Этот email уже используется другим аккаунтом",
        )
    except IntegrityError:
        # The users.email UNIQUE constraint is the final guard for concurrent
        # verification of the same address by two accounts.
        await db_session.rollback()
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="EMAIL_ALREADY_EXISTS",
            message="Этот email уже используется другим аккаунтом",
        )

    if user is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_TOKEN_INVALID",
            message="Ссылка недействительна, устарела или уже использована",
        )

    # Registration has no session yet; email-change verification rotates
    # session_version. Clearing the refresh cookie is safe in both cases.
    clear_refresh_cookie(response)
    return response_success(
        email=user.email,
        message="Email подтверждён. Для продолжения войдите в WB Insight.",
    )


@router.post("/resend")
async def resend_email(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "auth.email_verification.resend"
    if not lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="EMAIL_VERIFICATION_NOT_CONFIGURED",
            message="Подтверждение email временно недоступно",
        )

    runtime = await get_mail_transport_runtime(db_session)
    if not runtime.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="EMAIL_VERIFICATION_DELIVERY_UNAVAILABLE",
            message="Отправка писем подтверждения временно недоступна",
        )

    data = await request.json()
    email = str(data.get("email") or "").strip().lower()
    if not email:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="INVALID_REQUEST", message="Укажите email")

    user = await get_user_by_email(db_session, email)
    if user is None or not user.is_active or user.email_verified_at is not None:
        return _generic_resend_response()

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lifecycle_config.EMAIL_VERIFICATION_RESEND_SECONDS)
    recent = await db_session.execute(
        select(MailMessage.id)
        .where(
            MailMessage.user_id == user.id,
            MailMessage.template_code == "email_verification",
            MailMessage.created_at >= cutoff,
        )
        .limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        return _generic_resend_response()

    bucket = int(datetime.now(timezone.utc).timestamp() // lifecycle_config.EMAIL_VERIFICATION_RESEND_SECONDS)
    await queue_transactional_email(
        db_session,
        user=user,
        template_code="email_verification",
        recipient_email=user.email,
        idempotency_key=f"verify-resend:{user.id}:{bucket}",
    )
    return _generic_resend_response()
