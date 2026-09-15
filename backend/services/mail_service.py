import asyncio
import smtplib
from email.message import EmailMessage

from core.lifecycle_config import lifecycle_config as config


def _send_message(message: EmailMessage) -> None:
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT_SECONDS) as smtp:
        if config.SMTP_STARTTLS:
            smtp.starttls()
        if config.SMTP_USERNAME:
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD or "")
        smtp.send_message(message)


async def send_password_reset_email(email: str, token: str) -> None:
    """Send a reset link without ever logging or persisting the raw token."""
    reset_url = f"{config.PASSWORD_RESET_BASE_URL.rstrip('/')}?token={token}"
    message = EmailMessage()
    message["Subject"] = "Восстановление доступа к WB Insight"
    message["From"] = config.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "Для установки нового пароля откройте ссылку:\n\n"
        f"{reset_url}\n\n"
        f"Ссылка действует {config.PASSWORD_RESET_TOKEN_TTL_MINUTES} минут. "
        "Если вы не запрашивали восстановление, проигнорируйте письмо."
    )
    await asyncio.to_thread(_send_message, message)
