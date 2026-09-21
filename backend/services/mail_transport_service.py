from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config
from integrations.mail.smtp import SMTPMailProvider
from models.mail_delivery import MailProviderConfig
from settings import config
from utils.secret_crypto import decrypt_secret_payload, encrypt_secret_payload


_PROVIDER = "smtp"


@dataclass(frozen=True)
class MailTransportRuntime:
    MAIL_PROVIDER: str
    MAIL_DELIVERY_ENABLED: bool
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USERNAME: str | None
    SMTP_PASSWORD: str | None
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str
    SMTP_REPLY_TO_EMAIL: str | None
    SMTP_STARTTLS: bool
    SMTP_TIMEOUT_SECONDS: float
    source: str
    updated_at: str | None = None

    @property
    def credentials_configured(self) -> bool:
        return bool(self.SMTP_USERNAME and self.SMTP_PASSWORD)

    @property
    def ready(self) -> bool:
        if self.MAIL_PROVIDER != "smtp":
            return False
        if not self.SMTP_HOST or not self.SMTP_FROM_EMAIL:
            return False
        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            return False
        return True


def _secret_context() -> str:
    return "mail-provider:smtp"


def _read_secrets(row: MailProviderConfig | None) -> dict[str, Any]:
    if row is None or not row.encrypted_secrets:
        return {}
    return decrypt_secret_payload(
        row.encrypted_secrets,
        context=_secret_context(),
    )


async def get_mail_provider_config(
    session: AsyncSession | None,
) -> MailProviderConfig | None:
    if session is None:
        return None
    result = await session.execute(
        select(MailProviderConfig).where(MailProviderConfig.provider == _PROVIDER)
    )
    return result.scalar_one_or_none()


async def get_mail_transport_runtime(
    session: AsyncSession | None,
) -> MailTransportRuntime:
    source_mode = lifecycle_config.MAIL_CONFIG_SOURCE
    row = await get_mail_provider_config(session) if source_mode != "environment" else None

    if source_mode == "environment" or (source_mode == "auto" and row is None):
        return MailTransportRuntime(
            MAIL_PROVIDER=lifecycle_config.MAIL_PROVIDER,
            MAIL_DELIVERY_ENABLED=lifecycle_config.MAIL_DELIVERY_ENABLED,
            SMTP_HOST=lifecycle_config.SMTP_HOST,
            SMTP_PORT=int(lifecycle_config.SMTP_PORT),
            SMTP_USERNAME=lifecycle_config.SMTP_USERNAME,
            SMTP_PASSWORD=lifecycle_config.SMTP_PASSWORD,
            SMTP_FROM_EMAIL=lifecycle_config.SMTP_FROM_EMAIL,
            SMTP_FROM_NAME=lifecycle_config.SMTP_FROM_NAME,
            SMTP_REPLY_TO_EMAIL=lifecycle_config.SMTP_REPLY_TO_EMAIL,
            SMTP_STARTTLS=bool(lifecycle_config.SMTP_STARTTLS),
            SMTP_TIMEOUT_SECONDS=float(lifecycle_config.SMTP_TIMEOUT_SECONDS),
            source="environment" if lifecycle_config.SMTP_HOST else (
                "database" if source_mode == "database" else "unconfigured"
            ),
        )

    if row is None:
        return MailTransportRuntime(
            MAIL_PROVIDER="smtp",
            MAIL_DELIVERY_ENABLED=False,
            SMTP_HOST="",
            SMTP_PORT=587,
            SMTP_USERNAME=None,
            SMTP_PASSWORD=None,
            SMTP_FROM_EMAIL="",
            SMTP_FROM_NAME="WB Insight",
            SMTP_REPLY_TO_EMAIL=None,
            SMTP_STARTTLS=True,
            SMTP_TIMEOUT_SECONDS=10.0,
            source="database",
        )

    secrets = _read_secrets(row)
    return MailTransportRuntime(
        MAIL_PROVIDER=row.provider,
        MAIL_DELIVERY_ENABLED=bool(row.enabled),
        SMTP_HOST=str(row.host or ""),
        SMTP_PORT=int(row.port),
        SMTP_USERNAME=str(secrets.get("username") or "") or None,
        SMTP_PASSWORD=str(secrets.get("password") or "") or None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=str(row.reply_to_email or "") or None,
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


async def mail_transport_payload(session: AsyncSession) -> dict[str, Any]:
    runtime = await get_mail_transport_runtime(session)
    username_hint = None
    if runtime.SMTP_USERNAME:
        value = runtime.SMTP_USERNAME
        username_hint = (
            "•" * len(value)
            if len(value) <= 4
            else f"{value[:2]}{'•' * max(4, len(value) - 4)}{value[-2:]}"
        )
    return {
        "provider": runtime.MAIL_PROVIDER,
        "enabled": runtime.MAIL_DELIVERY_ENABLED,
        "ready": runtime.ready,
        "source": runtime.source,
        "host": runtime.SMTP_HOST,
        "port": runtime.SMTP_PORT,
        "from_email": runtime.SMTP_FROM_EMAIL,
        "from_name": runtime.SMTP_FROM_NAME,
        "reply_to_email": runtime.SMTP_REPLY_TO_EMAIL,
        "starttls": runtime.SMTP_STARTTLS,
        "timeout_seconds": runtime.SMTP_TIMEOUT_SECONDS,
        "credentials_configured": runtime.credentials_configured,
        "username_hint": username_hint,
        "updated_at": runtime.updated_at,
        "config_source": lifecycle_config.MAIL_CONFIG_SOURCE,
        "editable": lifecycle_config.MAIL_CONFIG_SOURCE in {"auto", "database"},
    }


async def upsert_mail_transport(
    session: AsyncSession,
    *,
    actor_id: UUID,
    values: dict[str, Any],
) -> MailProviderConfig:
    if lifecycle_config.MAIL_CONFIG_SOURCE == "environment":
        raise ValueError(
            "SMTP управляется ENV. Установите MAIL_CONFIG_SOURCE=auto или database для настройки из панели"
        )

    row = await get_mail_provider_config(session)
    if row is None:
        row = MailProviderConfig(provider=_PROVIDER)
        session.add(row)
        await session.flush()

    if "enabled" in values:
        row.enabled = bool(values["enabled"])

    if "host" in values:
        row.host = str(values.get("host") or "").strip() or None

    if "from_email" in values:
        from_email = str(values.get("from_email") or "").strip()
        if from_email and ("@" not in from_email or len(from_email) > 320):
            raise ValueError("Укажите корректный email отправителя")
        row.from_email = from_email or None

    if "from_name" in values:
        from_name = str(values.get("from_name") or "").strip()
        if len(from_name) > 160:
            raise ValueError("Имя отправителя не должно превышать 160 символов")
        row.from_name = from_name or "WB Insight"

    if "reply_to_email" in values:
        reply_to = str(values.get("reply_to_email") or "").strip()
        if reply_to and ("@" not in reply_to or len(reply_to) > 320):
            raise ValueError("Укажите корректный Reply-To email")
        row.reply_to_email = reply_to or None

    if "port" in values:
        port = int(values["port"])
        if port <= 0 or port > 65535:
            raise ValueError("SMTP port должен быть от 1 до 65535")
        row.port = port

    if "timeout_seconds" in values:
        timeout = int(values["timeout_seconds"])
        if timeout <= 0 or timeout > 120:
            raise ValueError("SMTP timeout должен быть от 1 до 120 секунд")
        row.timeout_seconds = timeout

    if "starttls" in values:
        row.starttls = bool(values["starttls"])

    existing = _read_secrets(row)
    if bool(values.get("clear_credentials")):
        existing = {}
    else:
        if "username" in values:
            username = str(values.get("username") or "").strip()
            if username:
                existing["username"] = username
            elif values.get("username") == "":
                existing.pop("username", None)
        if "password" in values:
            password = str(values.get("password") or "")
            if password:
                existing["password"] = password

    if bool(existing.get("username")) != bool(existing.get("password")):
        raise ValueError("SMTP username и password должны быть настроены вместе")

    row.encrypted_secrets = (
        encrypt_secret_payload(existing, context=_secret_context())
        if existing
        else None
    )
    row.updated_by = actor_id

    runtime = MailTransportRuntime(
        MAIL_PROVIDER=row.provider,
        MAIL_DELIVERY_ENABLED=bool(row.enabled),
        SMTP_HOST=str(row.host or ""),
        SMTP_PORT=int(row.port),
        SMTP_USERNAME=str(existing.get("username") or "") or None,
        SMTP_PASSWORD=str(existing.get("password") or "") or None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=str(row.reply_to_email or "") or None,
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
    )
    if not runtime.ready:
        raise ValueError(
            "Заполните host, from email и согласованную пару username/password"
        )
    if config.IS_PRODUCTION and not runtime.SMTP_STARTTLS:
        raise ValueError("В production SMTP должен использовать STARTTLS")

    await session.flush()
    return row



async def send_mail_transport_test(
    session: AsyncSession,
    *,
    recipient_email: str,
) -> str:
    recipient = str(recipient_email or "").strip().lower()
    if not recipient or "@" not in recipient or len(recipient) > 320:
        raise ValueError("Укажите корректный email для теста")

    runtime = await get_mail_transport_runtime(session)
    if not runtime.ready:
        raise RuntimeError("Почтовый шлюз ещё не готов: заполните обязательные SMTP-поля")

    provider = SMTPMailProvider(runtime)
    receipt = await provider.send(
        sender=runtime.SMTP_FROM_EMAIL,
        sender_name=runtime.SMTP_FROM_NAME,
        reply_to=runtime.SMTP_REPLY_TO_EMAIL,
        recipient=recipient,
        subject="[TEST] WB Insight · проверка почтового шлюза",
        body=(
            "Почтовый шлюз WB Insight настроен корректно.\n\n"
            "Это тестовое письмо из Панели управления."
        ),
        html_body=(
            '<!doctype html><html><body style="font-family:Arial,sans-serif;'
            'background:#f5f6fb;padding:24px;color:#182033;">'
            '<div style="max-width:620px;margin:auto;background:#fff;padding:28px;'
            'border-radius:14px;"><h2 style="margin-top:0;">Почтовый шлюз работает</h2>'
            '<p>WB Insight успешно отправил тестовое письмо через текущую SMTP-конфигурацию.</p>'
            '</div></body></html>'
        ),
    )
    return receipt.provider_message_id or ""
