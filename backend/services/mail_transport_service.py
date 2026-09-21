from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config
from integrations.mail.rusender import RuSenderMailProvider
from integrations.mail.smtp import SMTPMailProvider
from models.mail_delivery import MailProviderConfig
from settings import config
from utils.secret_crypto import decrypt_secret_payload, encrypt_secret_payload


_SUPPORTED_PROVIDERS = {"smtp", "rusender"}
_DEFAULT_RUSENDER_API_BASE_URL = "https://api.rusender.ru"


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
    RUSENDER_API_BASE_URL: str = _DEFAULT_RUSENDER_API_BASE_URL
    RUSENDER_KEY_ID: str | None = None
    RUSENDER_API_TOKEN: str | None = None
    RUSENDER_TIMEOUT_SECONDS: float = 10.0
    diagnostic_code: str | None = None

    @property
    def credentials_configured(self) -> bool:
        if self.MAIL_PROVIDER == "rusender":
            return bool(self.RUSENDER_KEY_ID and self.RUSENDER_API_TOKEN)
        return bool(self.SMTP_USERNAME and self.SMTP_PASSWORD)

    @property
    def ready(self) -> bool:
        if not self.SMTP_FROM_EMAIL:
            return False
        if self.MAIL_PROVIDER == "smtp":
            if not self.SMTP_HOST:
                return False
            return bool(self.SMTP_USERNAME) == bool(self.SMTP_PASSWORD)
        if self.MAIL_PROVIDER == "rusender":
            return bool(
                self.RUSENDER_API_BASE_URL
                and self.RUSENDER_KEY_ID
                and self.RUSENDER_API_TOKEN
            )
        return False


def _secret_context(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in _SUPPORTED_PROVIDERS:
        raise ValueError("Неподдерживаемый почтовый транспорт")
    return f"mail-provider:{normalized}"


def _read_secrets(row: MailProviderConfig | None) -> dict[str, Any]:
    if row is None or not row.encrypted_secrets:
        return {}
    return decrypt_secret_payload(
        row.encrypted_secrets,
        context=_secret_context(row.provider),
    )


async def get_mail_provider_config(
    session: AsyncSession | None,
) -> MailProviderConfig | None:
    """Return the effective database mail transport.

    The table predates multiple adapters. To stay migration-free, we keep one
    effective row and allow its provider code to switch between smtp/rusender.
    If legacy duplicate supported rows exist, the most recently updated one is
    treated as effective and the next save consolidates configuration.
    """
    if session is None:
        return None
    result = await session.execute(
        select(MailProviderConfig)
        .where(MailProviderConfig.provider.in_(_SUPPORTED_PROVIDERS))
        .order_by(MailProviderConfig.updated_at.desc(), MailProviderConfig.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _unconfigured_runtime(
    *,
    source: str,
    provider: str = "smtp",
    diagnostic_code: str | None = None,
) -> MailTransportRuntime:
    return MailTransportRuntime(
        MAIL_PROVIDER=provider if provider in _SUPPORTED_PROVIDERS else "smtp",
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
        RUSENDER_API_BASE_URL=_DEFAULT_RUSENDER_API_BASE_URL,
        source=source,
        diagnostic_code=diagnostic_code,
    )


def _environment_runtime() -> MailTransportRuntime:
    provider = lifecycle_config.MAIL_PROVIDER
    return MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=(lifecycle_config.MAIL_DELIVERY_ENABLED if provider == "smtp" else False),
        SMTP_HOST=lifecycle_config.SMTP_HOST,
        SMTP_PORT=int(lifecycle_config.SMTP_PORT),
        SMTP_USERNAME=lifecycle_config.SMTP_USERNAME,
        SMTP_PASSWORD=lifecycle_config.SMTP_PASSWORD,
        SMTP_FROM_EMAIL=lifecycle_config.SMTP_FROM_EMAIL,
        SMTP_FROM_NAME=lifecycle_config.SMTP_FROM_NAME,
        SMTP_REPLY_TO_EMAIL=lifecycle_config.SMTP_REPLY_TO_EMAIL,
        SMTP_STARTTLS=bool(lifecycle_config.SMTP_STARTTLS),
        SMTP_TIMEOUT_SECONDS=float(lifecycle_config.SMTP_TIMEOUT_SECONDS),
        RUSENDER_API_BASE_URL=lifecycle_config.RUSENDER_API_BASE_URL,
        RUSENDER_KEY_ID=lifecycle_config.RUSENDER_KEY_ID or None,
        RUSENDER_API_TOKEN=lifecycle_config.RUSENDER_API_TOKEN,
        RUSENDER_TIMEOUT_SECONDS=float(lifecycle_config.RUSENDER_TIMEOUT_SECONDS),
        source="environment",
    )


async def get_mail_transport_runtime(
    session: AsyncSession | None,
) -> MailTransportRuntime:
    source_mode = lifecycle_config.MAIL_CONFIG_SOURCE
    row = await get_mail_provider_config(session) if source_mode != "environment" else None

    if source_mode == "environment":
        return _environment_runtime()

    if source_mode == "auto" and row is None:
        runtime = _environment_runtime()
        if not runtime.ready:
            return _unconfigured_runtime(
                source="unconfigured",
                provider=runtime.MAIL_PROVIDER,
                diagnostic_code="environment_fallback_incomplete",
            )
        if (
            runtime.MAIL_PROVIDER == "rusender"
            and lifecycle_config.MAIL_DELIVERY_ENABLED
        ):
            return _unconfigured_runtime(
                source="unconfigured",
                provider=runtime.MAIL_PROVIDER,
                diagnostic_code="environment_fallback_invalid",
            )
        try:
            # Startup validation deliberately cannot inspect DB configuration.
            # Once runtime selection knows DB has no provider row, validate the
            # environment fallback before it becomes effective.
            lifecycle_config._validate_mail_transport(
                production=config.IS_PRODUCTION,
            )
        except RuntimeError:
            return _unconfigured_runtime(
                source="unconfigured",
                provider=runtime.MAIL_PROVIDER,
                diagnostic_code="environment_fallback_invalid",
            )
        return runtime

    if row is None:
        return _unconfigured_runtime(
            source="database",
            diagnostic_code="database_transport_missing",
        )

    secrets = _read_secrets(row)
    provider = str(row.provider or "smtp").lower()
    runtime = MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=(bool(row.enabled) if provider == "smtp" else False),
        SMTP_HOST=str(row.host or "") if provider == "smtp" else "",
        SMTP_PORT=int(row.port),
        SMTP_USERNAME=str(secrets.get("username") or "") or None,
        SMTP_PASSWORD=str(secrets.get("password") or "") or None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=str(row.reply_to_email or "") or None,
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        RUSENDER_API_BASE_URL=(
            str(row.host or _DEFAULT_RUSENDER_API_BASE_URL)
            if provider == "rusender"
            else _DEFAULT_RUSENDER_API_BASE_URL
        ),
        RUSENDER_KEY_ID=str(secrets.get("key_id") or "") or None,
        RUSENDER_API_TOKEN=str(secrets.get("api_token") or "") or None,
        RUSENDER_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )
    if not runtime.ready:
        return MailTransportRuntime(
            **{
                **runtime.__dict__,
                "diagnostic_code": "database_transport_incomplete",
            }
        )
    return runtime


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
    unsubscribe_configured = bool(
        lifecycle_config.MAIL_UNSUBSCRIBE_BASE_URL
        and len(lifecycle_config.MAIL_UNSUBSCRIBE_HMAC_KEY) >= 32
    )
    # The native RuSender transactional endpoint documents custom X-* headers
    # only, so the app does not claim RFC 8058 marketing readiness on that
    # adapter. Campaigns can later use RuSender's campaign API separately.
    marketing_transport_supported = runtime.MAIL_PROVIDER == "smtp"

    return {
        "provider": runtime.MAIL_PROVIDER,
        "enabled": runtime.MAIL_DELIVERY_ENABLED,
        "ready": runtime.ready,
        "marketing_ready": bool(
            runtime.ready
            and runtime.MAIL_DELIVERY_ENABLED
            and unsubscribe_configured
            and marketing_transport_supported
        ),
        "marketing_transport_supported": marketing_transport_supported,
        "unsubscribe_configured": unsubscribe_configured,
        "source": runtime.source,
        "host": runtime.SMTP_HOST,
        "port": runtime.SMTP_PORT,
        "api_base_url": runtime.RUSENDER_API_BASE_URL,
        "key_id": runtime.RUSENDER_KEY_ID,
        "from_email": runtime.SMTP_FROM_EMAIL,
        "from_name": runtime.SMTP_FROM_NAME,
        "reply_to_email": runtime.SMTP_REPLY_TO_EMAIL,
        "starttls": runtime.SMTP_STARTTLS,
        "timeout_seconds": (
            runtime.RUSENDER_TIMEOUT_SECONDS
            if runtime.MAIL_PROVIDER == "rusender"
            else runtime.SMTP_TIMEOUT_SECONDS
        ),
        "credentials_configured": runtime.credentials_configured,
        "username_hint": username_hint,
        "updated_at": runtime.updated_at,
        "config_source": lifecycle_config.MAIL_CONFIG_SOURCE,
        "editable": lifecycle_config.MAIL_CONFIG_SOURCE in {"auto", "database"},
        "diagnostic_code": runtime.diagnostic_code,
        "system_mail": {
            "email_verification": {
                "enabled": lifecycle_config.EMAIL_VERIFICATION_ENABLED,
                "base_url_configured": bool(lifecycle_config.EMAIL_VERIFICATION_BASE_URL),
                "ready": bool(
                    runtime.ready
                    and lifecycle_config.EMAIL_VERIFICATION_ENABLED
                    and lifecycle_config.EMAIL_VERIFICATION_BASE_URL
                ),
                "ttl_minutes": lifecycle_config.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES,
                "resend_seconds": lifecycle_config.EMAIL_VERIFICATION_RESEND_SECONDS,
            },
            "password_reset": {
                "enabled": lifecycle_config.PASSWORD_RESET_ENABLED,
                "base_url_configured": bool(lifecycle_config.PASSWORD_RESET_BASE_URL),
                "ready": bool(
                    runtime.ready
                    and lifecycle_config.PASSWORD_RESET_ENABLED
                    and lifecycle_config.PASSWORD_RESET_BASE_URL
                ),
                "ttl_minutes": lifecycle_config.PASSWORD_RESET_TOKEN_TTL_MINUTES,
                "resend_seconds": lifecycle_config.PASSWORD_RESET_RESEND_SECONDS,
            },
        },
        "deliverability": {
            "tls": bool(
                runtime.MAIL_PROVIDER == "rusender"
                or runtime.SMTP_STARTTLS
            ),
            "sender_identity": bool(runtime.SMTP_FROM_EMAIL and runtime.SMTP_FROM_NAME),
            "reply_to_configured": bool(runtime.SMTP_REPLY_TO_EMAIL and runtime.MAIL_PROVIDER == "smtp"),
            "one_click_unsubscribe": bool(
                unsubscribe_configured and marketing_transport_supported
            ),
            "spf": "external",
            "dkim": "external",
            "dmarc": "external",
            "ptr": "provider" if runtime.MAIL_PROVIDER == "rusender" else "external",
        },
    }


async def upsert_mail_transport(
    session: AsyncSession,
    *,
    actor_id: UUID,
    values: dict[str, Any],
) -> MailProviderConfig:
    if lifecycle_config.MAIL_CONFIG_SOURCE == "environment":
        raise ValueError(
            "Почтовый транспорт управляется ENV. Установите MAIL_CONFIG_SOURCE=auto или database для настройки из панели"
        )

    provider = str(values.get("provider") or "").strip().lower()
    if not provider:
        current = await get_mail_provider_config(session)
        provider = str(current.provider if current is not None else "smtp").lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError("Поддерживаются только SMTP и RuSender API")

    row = await get_mail_provider_config(session)
    existing: dict[str, Any] = {}
    if row is None:
        row = MailProviderConfig(provider=provider)
        session.add(row)
        await session.flush()
    elif str(row.provider).lower() == provider:
        existing = _read_secrets(row)
    else:
        # Provider switch is intentionally destructive for old credentials:
        # secrets encrypted under one provider context are never re-used by the
        # other adapter.
        row.provider = provider
        row.encrypted_secrets = None
        row.host = None
        row.port = 443 if provider == "rusender" else 587
        row.starttls = provider == "smtp"
        existing = {}

    if provider == "rusender":
        row.enabled = False
    elif "enabled" in values:
        row.enabled = bool(values["enabled"])

    if "from_email" in values:
        from_email = str(values.get("from_email") or "").strip().lower()
        if from_email and ("@" not in from_email or len(from_email) > 320):
            raise ValueError("Укажите корректный email отправителя")
        row.from_email = from_email or None

    if "from_name" in values:
        from_name = str(values.get("from_name") or "").strip()
        if len(from_name) > 160:
            raise ValueError("Имя отправителя не должно превышать 160 символов")
        row.from_name = from_name or "WB Insight"

    if "reply_to_email" in values:
        reply_to = str(values.get("reply_to_email") or "").strip().lower()
        if reply_to and ("@" not in reply_to or len(reply_to) > 320):
            raise ValueError("Укажите корректный Reply-To email")
        row.reply_to_email = reply_to or None

    if "timeout_seconds" in values:
        timeout = int(values["timeout_seconds"])
        if timeout <= 0 or timeout > 120:
            raise ValueError("Timeout должен быть от 1 до 120 секунд")
        row.timeout_seconds = timeout

    if bool(values.get("clear_credentials")):
        existing = {}

    if provider == "smtp":
        if "host" in values:
            row.host = str(values.get("host") or "").strip() or None
        if "port" in values:
            port = int(values["port"])
            if port <= 0 or port > 65535:
                raise ValueError("SMTP port должен быть от 1 до 65535")
            row.port = port
        if "starttls" in values:
            row.starttls = bool(values["starttls"])

        if not bool(values.get("clear_credentials")):
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
    else:
        # The DB-managed RuSender adapter is pinned to the official API origin
        # so an administrative setting cannot redirect the bearer token to an
        # arbitrary host.
        row.host = _DEFAULT_RUSENDER_API_BASE_URL
        row.port = 443
        row.starttls = True

        key_id = str(values.get("key_id") or existing.get("key_id") or "").strip()
        if key_id and not key_id.isdigit():
            raise ValueError("RuSender key ID должен быть числом")
        if key_id:
            existing["key_id"] = key_id
        else:
            existing.pop("key_id", None)

        if not bool(values.get("clear_credentials")) and "api_token" in values:
            api_token = str(values.get("api_token") or "").strip()
            if api_token:
                existing["api_token"] = api_token
        if bool(values.get("clear_credentials")):
            existing.pop("api_token", None)

    row.encrypted_secrets = (
        encrypt_secret_payload(existing, context=_secret_context(provider))
        if existing
        else None
    )
    row.updated_by = actor_id

    runtime = MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=bool(row.enabled),
        SMTP_HOST=str(row.host or "") if provider == "smtp" else "",
        SMTP_PORT=int(row.port),
        SMTP_USERNAME=str(existing.get("username") or "") or None,
        SMTP_PASSWORD=str(existing.get("password") or "") or None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=str(row.reply_to_email or "") or None,
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        RUSENDER_API_BASE_URL=(
            str(row.host or _DEFAULT_RUSENDER_API_BASE_URL)
            if provider == "rusender"
            else _DEFAULT_RUSENDER_API_BASE_URL
        ),
        RUSENDER_KEY_ID=str(existing.get("key_id") or "") or None,
        RUSENDER_API_TOKEN=str(existing.get("api_token") or "") or None,
        RUSENDER_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
    )
    if not runtime.ready:
        if provider == "rusender":
            raise ValueError("Заполните key ID, API token и email отправителя RuSender")
        raise ValueError(
            "Заполните host, from email и согласованную пару username/password"
        )
    if config.IS_PRODUCTION and provider == "smtp" and not runtime.SMTP_STARTTLS:
        raise ValueError("В production SMTP должен использовать STARTTLS")
    if config.IS_PRODUCTION and provider == "rusender" and not runtime.RUSENDER_API_BASE_URL.startswith("https://"):
        raise ValueError("В production RuSender API должен использовать HTTPS")

    await session.flush()
    return row


def mail_provider_for_runtime(runtime: MailTransportRuntime):
    if runtime.MAIL_PROVIDER == "rusender":
        return RuSenderMailProvider(runtime)
    if runtime.MAIL_PROVIDER == "smtp":
        return SMTPMailProvider(runtime)
    raise RuntimeError("mail_transport_not_supported")


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
        raise RuntimeError("Почтовый шлюз ещё не готов: заполните обязательные поля")

    provider = mail_provider_for_runtime(runtime)
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
            '<p>WB Insight успешно отправил тестовое письмо через текущий транспорт.</p>'
            '</div></body></html>'
        ),
        idempotency_key=f"gateway-test:{uuid4()}",
    )
    return receipt.provider_message_id or ""
