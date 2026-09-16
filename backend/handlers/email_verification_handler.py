from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from models.mail_delivery import MailMessage
from services.email_verification_service import verify_email
from services.mail_service import queue_transactional_email
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
    data = await request.json()
    raw_token = str(data.get("token") or "").strip()
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="EMAIL_VERIFICATION_TOKEN_REQUIRED", message="Отсутствует код подтверждения")

    user = await verify_email(db_session, raw_token)
    if user is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_VERIFICATION_TOKEN_INVALID",
            message="Ссылка недействительна или срок её действия истёк",
        )
    return response_success(message="Email подтверждён. Теперь можно войти в WB Insight.")


@router.post("/resend")
async def resend_email(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="EMAIL_VERIFICATION_NOT_CONFIGURED",
            message="Подтверждение email временно недоступно",
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
        idempotency_key=f"verify-resend:{user.id}:{bucket}",
    )
    return _generic_resend_response()
