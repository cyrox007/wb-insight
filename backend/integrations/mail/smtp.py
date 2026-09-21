import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from integrations.mail.provider import MailDeliveryReceipt


class SMTPMailProvider:
    code = "smtp"

    def __init__(self, config) -> None:
        self._config = config

    def _send_sync(
        self,
        *,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> str:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient
        message_id = make_msgid(domain=(sender.rpartition("@")[2] or None))
        message["Message-ID"] = message_id
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(
            self._config.SMTP_HOST,
            self._config.SMTP_PORT,
            timeout=self._config.SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            if self._config.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if self._config.SMTP_USERNAME:
                smtp.login(
                    self._config.SMTP_USERNAME,
                    self._config.SMTP_PASSWORD or "",
                )
            smtp.send_message(message)
        return message_id

    async def send(
        self,
        *,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> MailDeliveryReceipt:
        provider_message_id = await asyncio.to_thread(
            self._send_sync,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            html_body=html_body,
        )
        return MailDeliveryReceipt(provider_message_id=provider_message_id)
