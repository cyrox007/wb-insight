import asyncio
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from html import escape

from integrations.mail.provider import (
    MailDeliveryReceipt,
    MailProviderCapabilities,
    MailProviderError,
)


class SMTPMailProvider:
    code = "smtp"
    display_name = "SMTP"
    configuration_kind = "smtp"
    default_port = 587
    default_api_base_url = None
    key_id_numeric = False
    capabilities = MailProviderCapabilities(
        transport_kind="smtp",
        transactional=True,
        marketing=True,
        custom_headers=True,
        rfc_headers=True,
        one_click_unsubscribe=True,
        reply_to=True,
        preview_title=True,
        idempotency_key=False,
        provider_managed_tls=False,
        provider_managed_ptr=False,
        outbound_port=None,
    )

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
        recipient_name: str | None = None,
        preview_title: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((sender_name or "", sender)) if sender_name else sender
        message["To"] = formataddr((recipient_name or "", recipient)) if recipient_name else recipient
        if reply_to:
            message["Reply-To"] = reply_to
        message["Date"] = format_datetime(datetime.now(timezone.utc))
        message_id = make_msgid(domain=(sender.rpartition("@")[2] or None))
        message["Message-ID"] = message_id

        reserved = {
            "from",
            "to",
            "subject",
            "date",
            "message-id",
            "reply-to",
            "mime-version",
            "content-type",
        }
        for key, value in (headers or {}).items():
            name = str(key or "").strip()
            header_value = str(value or "").strip()
            if not name or not header_value or name.lower() in reserved:
                continue
            if "\r" in name or "\n" in name or "\r" in header_value or "\n" in header_value:
                raise ValueError("Недопустимый почтовый заголовок")
            message[name] = header_value

        message.set_content(body)
        if html_body:
            html_payload = html_body
            if preview_title:
                preheader = (
                    '<div style="display:none!important;visibility:hidden;opacity:0;'
                    'color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">'
                    + escape(str(preview_title))
                    + "</div>"
                )
                html_payload = preheader + html_payload
            message.add_alternative(html_payload, subtype="html")

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
        recipient_name: str | None = None,
        preview_title: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> MailDeliveryReceipt:
        try:
            provider_message_id = await asyncio.to_thread(
                self._send_sync,
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                html_body=html_body,
                sender_name=sender_name,
                recipient_name=recipient_name,
                preview_title=preview_title,
                reply_to=reply_to,
                headers=headers,
            )
        except smtplib.SMTPAuthenticationError as exc:
            raise MailProviderError(
                "smtp_authentication_failed",
                provider_code=self.code,
                retryable=False,
                user_message="SMTP-сервер отклонил авторизацию. Проверьте логин и пароль.",
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise MailProviderError(
                "smtp_recipient_rejected",
                provider_code=self.code,
                retryable=False,
                user_message="SMTP-сервер отклонил адрес получателя тестового письма.",
            ) from exc
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as exc:
            raise MailProviderError(
                "smtp_connection_failed",
                provider_code=self.code,
                retryable=True,
                user_message=(
                    "Не удалось подключиться к SMTP-серверу. Проверьте адрес, порт "
                    "и доступность исходящего SMTP-соединения."
                ),
            ) from exc
        except smtplib.SMTPException as exc:
            raise MailProviderError(
                "smtp_delivery_failed",
                provider_code=self.code,
                retryable=True,
                user_message="SMTP-сервер не принял письмо. Проверьте настройки транспорта.",
            ) from exc

        return MailDeliveryReceipt(provider_message_id=provider_message_id)
