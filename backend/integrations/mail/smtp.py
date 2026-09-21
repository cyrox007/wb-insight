import asyncio
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

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
        sender_name: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((sender_name or "", sender)) if sender_name else sender
        message["To"] = recipient
        if reply_to:
            message["Reply-To"] = reply_to
        message["Date"] = format_datetime(datetime.now(timezone.utc))
        message_id = make_msgid(domain=(sender.rpartition("@")[2] or None))
        message["Message-ID"] = message_id

        reserved = {"from", "to", "subject", "date", "message-id", "reply-to", "mime-version", "content-type"}
        for key, value in (headers or {}).items():
            name = str(key or "").strip()
            header_value = str(value or "").strip()
            if not name or not header_value or name.lower() in reserved:
                continue
            if "\r" in name or "\n" in name or "\r" in header_value or "\n" in header_value:
                raise ValueError("unsafe_mail_header")
            message[name] = header_value
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
        sender_name: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> MailDeliveryReceipt:
        provider_message_id = await asyncio.to_thread(
            self._send_sync,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            html_body=html_body,
            sender_name=sender_name,
            reply_to=reply_to,
            headers=headers,
        )
        return MailDeliveryReceipt(provider_message_id=provider_message_id)
