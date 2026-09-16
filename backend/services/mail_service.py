import asyncio
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from urllib.parse import quote

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config as config
from models.mail_delivery import (
    CampaignStatus,
    MailCampaign,
    MailKind,
    MailMessage,
    MailStatus,
    MailSuppression,
)
from models.users_model import User
from services.account_lifecycle_service import issue_password_reset_token
from services.email_verification_service import issue_email_verification_token


TRANSACTIONAL_TEMPLATES = {"email_verification": 1, "password_reset": 1}


class PermanentMailDeliveryError(RuntimeError):
    """A safe deterministic failure that must not be retried."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code[:96]


def _normalized_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _token_url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}#token={quote(token, safe='')}"


def _send_message(message: EmailMessage) -> None:
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT_SECONDS) as smtp:
        if config.SMTP_STARTTLS:
            smtp.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD or "")
        smtp.send_message(message)


async def _smtp_send(recipient: str, subject: str, body: str) -> str:
    if not (
        config.MAIL_DELIVERY_ENABLED
        or config.PASSWORD_RESET_ENABLED
        or config.EMAIL_VERIFICATION_ENABLED
    ):
        raise RuntimeError("mail_delivery_disabled")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.SMTP_FROM_EMAIL
    message["To"] = recipient
    message_id = make_msgid(domain=(config.SMTP_FROM_EMAIL.rpartition("@")[2] or None))
    message["Message-ID"] = message_id
    message.set_content(body)
    await asyncio.to_thread(_send_message, message)
    return message_id


async def queue_transactional_email(
    session: AsyncSession,
    *,
    user: User,
    template_code: str,
    idempotency_key: str | None = None,
    recipient_email: str | None = None,
) -> MailMessage:
    if template_code not in TRANSACTIONAL_TEMPLATES:
        raise ValueError(f"Unknown transactional template: {template_code}")
    recipient = _normalized_email(recipient_email or user.email)
    if not recipient:
        raise ValueError("transactional_recipient_required")
    key = idempotency_key or f"{template_code}:{user.id}:{uuid.uuid4()}"
    existing = await session.execute(select(MailMessage).where(MailMessage.idempotency_key == key))
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    message = MailMessage(
        user_id=user.id,
        recipient_email=recipient,
        kind=MailKind.TRANSACTIONAL.value,
        template_code=template_code,
        template_version=TRANSACTIONAL_TEMPLATES[template_code],
        status=MailStatus.QUEUED.value,
        max_attempts=config.MAIL_MAX_ATTEMPTS,
        idempotency_key=key,
    )
    session.add(message)
    await session.flush()
    return message


async def queue_test_email(
    session: AsyncSession,
    *,
    recipient_email: str,
    subject: str,
    body: str,
    actor_id,
) -> MailMessage:
    message = MailMessage(
        user_id=actor_id,
        recipient_email=recipient_email.strip().lower(),
        kind=MailKind.TEST.value,
        subject=subject.strip()[:255],
        body=body,
        status=MailStatus.QUEUED.value,
        max_attempts=config.MAIL_MAX_ATTEMPTS,
        idempotency_key=f"test:{actor_id}:{uuid.uuid4()}",
    )
    session.add(message)
    await session.flush()
    return message


async def _render_transactional(session: AsyncSession, message: MailMessage) -> tuple[str, str]:
    if message.user_id is None:
        raise PermanentMailDeliveryError("mail_user_missing")
    result = await session.execute(select(User).where(User.id == message.user_id).with_for_update())
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise PermanentMailDeliveryError("mail_user_unavailable")

    recipient = _normalized_email(message.recipient_email)
    if message.template_code == "email_verification":
        try:
            raw_token = await issue_email_verification_token(session, user, email=recipient)
        except ValueError as exc:
            raise PermanentMailDeliveryError(str(exc) or "email_verification_target_stale") from exc
        verify_url = _token_url(config.EMAIL_VERIFICATION_BASE_URL, raw_token)
        is_change = recipient == _normalized_email(getattr(user, "pending_email", None))
        return (
            "Подтвердите новый email в WB Insight" if is_change else "Подтвердите email в WB Insight",
            (
                "Подтвердите новый адрес электронной почты для аккаунта WB Insight:\n\n"
                if is_change
                else "Подтвердите адрес электронной почты, чтобы завершить регистрацию:\n\n"
            )
            + f"{verify_url}\n\n"
            + f"Ссылка действует {config.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES} минут. "
            + "Если вы не запрашивали это действие, проигнорируйте письмо.",
        )

    if message.template_code == "password_reset":
        # A queued reset must never be delivered to an address that ceased to be
        # the account identity after the request was queued.
        if recipient != _normalized_email(user.email):
            raise PermanentMailDeliveryError("password_reset_target_stale")
        raw_token = await issue_password_reset_token(session, user)
        reset_url = _token_url(config.PASSWORD_RESET_BASE_URL, raw_token)
        return (
            "Восстановление доступа к WB Insight",
            "Для установки нового пароля откройте ссылку:\n\n"
            f"{reset_url}\n\n"
            f"Ссылка действует {config.PASSWORD_RESET_TOKEN_TTL_MINUTES} минут. "
            "Если вы не запрашивали восстановление, проигнорируйте письмо.",
        )

    raise PermanentMailDeliveryError("mail_template_unknown")


async def _is_suppressed(
    session: AsyncSession,
    email: str,
    *,
    user_id=None,
) -> bool:
    predicates = [MailSuppression.email == _normalized_email(email)]
    if user_id is not None:
        # User-scoped suppression survives a later verified email change.
        predicates.append(MailSuppression.user_id == user_id)
    result = await session.execute(
        select(MailSuppression.id).where(
            MailSuppression.active.is_(True),
            or_(*predicates),
        )
    )
    return result.scalar_one_or_none() is not None


async def deliver_message(session: AsyncSession, message_id) -> str:
    """Deliver one message inside caller-owned transaction.

    Delivery exceptions intentionally escape. The Celery task rolls the transaction
    back first, which also rolls back a freshly-issued reset/verification token,
    then records only a safe retry state in a new transaction.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(select(MailMessage).where(MailMessage.id == message_id).with_for_update())
    message = result.scalar_one_or_none()
    if message is None:
        return "missing"
    if message.status in {MailStatus.SENT.value, MailStatus.CANCELLED.value, MailStatus.SUPPRESSED.value}:
        return message.status
    if message.next_attempt_at and message.next_attempt_at > now:
        return "not_due"

    if message.kind == MailKind.CAMPAIGN.value and await _is_suppressed(
        session,
        message.recipient_email,
        user_id=message.user_id,
    ):
        message.status = MailStatus.SUPPRESSED.value
        message.safe_error_code = "suppressed"
        message.last_attempt_at = now
        await session.flush()
        return message.status

    message.status = MailStatus.SENDING.value
    message.last_attempt_at = now
    await session.flush()

    if message.kind == MailKind.TRANSACTIONAL.value:
        subject, body = await _render_transactional(session, message)
    else:
        subject = (message.subject or "WB Insight")[:255]
        body = message.body or ""

    provider_id = await _smtp_send(message.recipient_email, subject, body)
    message.attempt_count += 1
    message.provider_message_id = provider_id
    message.status = MailStatus.SENT.value
    message.safe_error_code = None
    message.sent_at = datetime.now(timezone.utc)
    await session.flush()
    return message.status


async def mark_message_failure(
    session: AsyncSession,
    message_id,
    error_code: str,
    *,
    terminal: bool = False,
) -> str:
    result = await session.execute(select(MailMessage).where(MailMessage.id == message_id).with_for_update())
    message = result.scalar_one_or_none()
    if message is None:
        return "missing"
    if message.status in {MailStatus.SENT.value, MailStatus.CANCELLED.value, MailStatus.SUPPRESSED.value}:
        return message.status
    message.attempt_count += 1
    message.last_attempt_at = datetime.now(timezone.utc)
    message.safe_error_code = (error_code or "delivery_error")[:96]
    if terminal or message.attempt_count >= message.max_attempts:
        message.status = MailStatus.FAILED.value
        # Prevent deterministic failures from being picked up again by due_message_ids.
        if terminal:
            message.attempt_count = message.max_attempts
    else:
        message.status = MailStatus.QUEUED.value
        delay = config.MAIL_RETRY_BASE_SECONDS * (2 ** max(message.attempt_count - 1, 0))
        message.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(delay, 3600))
    await session.flush()
    return message.status


async def due_message_ids(session: AsyncSession, limit: int | None = None) -> list:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(MailMessage.id)
        .where(
            MailMessage.status.in_([MailStatus.QUEUED.value, MailStatus.FAILED.value]),
            MailMessage.next_attempt_at <= now,
            MailMessage.attempt_count < MailMessage.max_attempts,
        )
        .order_by(MailMessage.created_at.asc())
        .limit(limit or config.MAIL_BATCH_SIZE)
    )
    return list(result.scalars().all())


async def refresh_campaign_counters(session: AsyncSession, campaign_id) -> None:
    campaign_result = await session.execute(select(MailCampaign).where(MailCampaign.id == campaign_id).with_for_update())
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        return
    rows = await session.execute(
        select(MailMessage.status, func.count(MailMessage.id))
        .where(MailMessage.campaign_id == campaign_id)
        .group_by(MailMessage.status)
    )
    counts = {mail_status: int(count) for mail_status, count in rows.all()}
    campaign.queued_count = counts.get(MailStatus.QUEUED.value, 0) + counts.get(MailStatus.SENDING.value, 0)
    campaign.sent_count = counts.get(MailStatus.SENT.value, 0)
    campaign.failed_count = counts.get(MailStatus.FAILED.value, 0)
    campaign.suppressed_count = counts.get(MailStatus.SUPPRESSED.value, 0)
    if campaign.queued_count > 0:
        campaign.status = CampaignStatus.SENDING.value
    elif campaign.sent_count + campaign.failed_count + campaign.suppressed_count >= campaign.audience_count:
        campaign.status = CampaignStatus.COMPLETED.value if campaign.failed_count == 0 else CampaignStatus.FAILED.value
        campaign.completed_at = datetime.now(timezone.utc)
    await session.flush()


async def send_password_reset_email(email: str, token: str) -> None:
    """Compatibility helper for legacy callers/tests; request flow uses the queue."""
    reset_url = _token_url(config.PASSWORD_RESET_BASE_URL, token)
    await _smtp_send(
        email,
        "Восстановление доступа к WB Insight",
        "Для установки нового пароля откройте ссылку:\n\n"
        f"{reset_url}\n\n"
        f"Ссылка действует {config.PASSWORD_RESET_TOKEN_TTL_MINUTES} минут. "
        "Если вы не запрашивали восстановление, проигнорируйте письмо.",
    )
