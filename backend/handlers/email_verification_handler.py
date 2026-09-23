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
from services.user_identity import normalize_email
from services.user_service import get_user_by_email
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/auth/email-verification", tags=["Подтверждение email"])


def _generic_resend_response() -> dict:
    return response_success(
        message="Если адрес зарегистрирован и ещё не подтверждён, письмо будет отправлено."
    )


def _is_email_identity_conflict(exc: IntegrityError) -> bool:
    """Определяет конфликт уникальности именно email identity пользователя."""
    known_constraints = {"users_email_key", "uq_users_email_lower"}
    original = getattr(exc, "orig", None)
    candidates = [
        getattr(original, "constraint_name", None),
        getattr(getattr(original, "__cause__", None), "constraint_name", None),
    ]
    if any(value in known_constraints for value in candidates):
        return True

    error_text = str(original or "").lower()
    return any(constraint in error_text for constraint in known_constraints)


@router.post("/confirm")
async def confirm_email(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    request.state.audit_action = "auth.email_verification.confirm"
    try:
        data = await request.json()
    except (TypeError, ValueError):
        data = None

    if not isinstance(data, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_PAYLOAD_INVALID",
            message="Ожидается JSON-объект с кодом подтверждения",
        )

    unsupported_fields = sorted(set(data) - {"token"})
    if unsupported_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_FIELDS_UNSUPPORTED",
            message="Запрос подтверждения email содержит неподдерживаемые поля",
        )

    token_value = data.get("token")
    raw_token = token_value.strip() if isinstance(token_value, str) else ""
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_TOKEN_REQUIRED",
            message="Отсутствует код подтверждения",
        )
    if len(raw_token) > 512:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_TOKEN_INVALID",
            message="Код подтверждения имеет некорректный формат",
        )

    try:
        async with db_session.begin_nested():
            user = await verify_email(db_session, raw_token)
    except EmailVerificationTargetConflict:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="EMAIL_ALREADY_EXISTS",
            message="Этот email уже используется другим аккаунтом",
        )
    except IntegrityError as exc:
        if not _is_email_identity_conflict(exc):
            raise
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

    # У регистрации ещё нет сессии, а подтверждение смены email ротирует
    # session_version. Очистка refresh-cookie безопасна в обоих сценариях.
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

    try:
        data = await request.json()
    except (TypeError, ValueError):
        data = None

    if not isinstance(data, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_PAYLOAD_INVALID",
            message="Ожидается JSON-объект с email",
        )

    unsupported_fields = sorted(set(data) - {"email"})
    if unsupported_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_FIELDS_UNSUPPORTED",
            message="Запрос повторной отправки содержит неподдерживаемые поля",
        )

    email = normalize_email(data.get("email"))
    if email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_INVALID",
            message="Укажите корректный email",
        )

    user = await get_user_by_email(db_session, email)
    if user is None or not user.is_active or user.email_verified_at is not None:
        return _generic_resend_response()

    resend_seconds = max(
        1,
        int(lifecycle_config.EMAIL_VERIFICATION_RESEND_SECONDS),
    )
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=resend_seconds)
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

    bucket = int(datetime.now(timezone.utc).timestamp() // resend_seconds)
    await queue_transactional_email(
        db_session,
        user=user,
        template_code="email_verification",
        recipient_email=user.email,
        idempotency_key=f"verify-resend:{user.id}:{bucket}",
    )
    return _generic_resend_response()
