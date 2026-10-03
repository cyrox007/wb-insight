from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config
from integrations.mail.resend import ResendMailProvider
from integrations.mail.rusender import RuSenderMailProvider
from integrations.mail.smtp import SMTPMailProvider
from models.mail_delivery import MailProviderConfig
from settings import config
from utils.secret_crypto import decrypt_secret_payload, encrypt_secret_payload


_PROVIDER_FACTORIES = {
    SMTPMailProvider.code: SMTPMailProvider,
    RuSenderMailProvider.code: RuSenderMailProvider,
    ResendMailProvider.code: ResendMailProvider,
}
_SUPPORTED_PROVIDERS = frozenset(_PROVIDER_FACTORIES)


def _provider_class(code: str):
    normalized = str(code or "").strip().lower()
    provider_class = _PROVIDER_FACTORIES.get(normalized)
    if provider_class is None:
        raise RuntimeError(
            f"Почтовый провайдер не зарегистрирован: {normalized or 'пустое значение'}"
        )
    return provider_class


def mail_provider_capabilities(code: str):
    return _provider_class(code).capabilities


def mail_provider_catalog() -> list[dict[str, Any]]:
    catalog = []
    for code in sorted(_SUPPORTED_PROVIDERS):
        provider_class = _provider_class(code)
        capabilities = provider_class.capabilities
        transport_label = (
            "HTTPS API"
            if capabilities.transport_kind == "https_api"
            else "SMTP"
        )
        outbound_port = capabilities.outbound_port
        connection_note = (
            f"{transport_label} · исходящий порт {outbound_port}"
            if outbound_port
            else transport_label
        )
        catalog.append(
            {
                "code": code,
                "label": provider_class.display_name,
                "connection_note": connection_note,
                "capabilities": capabilities.as_payload(),
                "configuration": {
                    "kind": provider_class.configuration_kind,
                    "api_base_url": provider_class.default_api_base_url,
                    "requires_key_id": provider_class.requires_key_id,
                    "key_id_numeric": provider_class.key_id_numeric,
                },
            }
        )
    return catalog


@dataclass(frozen=True, init=False)
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
    updated_at: str | None
    API_BASE_URL: str
    API_KEY_ID: str | None
    API_TOKEN: str | None
    API_TIMEOUT_SECONDS: float
    diagnostic_code: str | None

    def __init__(
        self,
        *,
        MAIL_PROVIDER: str,
        MAIL_DELIVERY_ENABLED: bool,
        SMTP_HOST: str,
        SMTP_PORT: int,
        SMTP_USERNAME: str | None,
        SMTP_PASSWORD: str | None,
        SMTP_FROM_EMAIL: str,
        SMTP_FROM_NAME: str,
        SMTP_REPLY_TO_EMAIL: str | None,
        SMTP_STARTTLS: bool,
        SMTP_TIMEOUT_SECONDS: float,
        source: str,
        updated_at: str | None = None,
        API_BASE_URL: str = "",
        API_KEY_ID: str | None = None,
        API_TOKEN: str | None = None,
        API_TIMEOUT_SECONDS: float = 10.0,
        diagnostic_code: str | None = None,
        **legacy: Any,
    ) -> None:
        # Поддержка старых имён нужна только на переходный период для тестов и
        # исторических внутренних вызовов. В runtime сохраняются нейтральные поля.
        if not API_BASE_URL:
            API_BASE_URL = str(legacy.pop("RUSENDER_API_BASE_URL", "") or "")
        if API_KEY_ID is None:
            API_KEY_ID = str(legacy.pop("RUSENDER_KEY_ID", "") or "") or None
        if API_TOKEN is None:
            API_TOKEN = str(legacy.pop("RUSENDER_API_TOKEN", "") or "") or None
        legacy_timeout = legacy.pop("RUSENDER_TIMEOUT_SECONDS", None)
        if legacy_timeout is not None and API_TIMEOUT_SECONDS == 10.0:
            API_TIMEOUT_SECONDS = float(legacy_timeout)
        if legacy:
            unknown = ", ".join(sorted(legacy))
            raise TypeError(f"Неизвестные параметры почтового runtime: {unknown}")

        values = {
            "MAIL_PROVIDER": str(MAIL_PROVIDER or "").strip().lower(),
            "MAIL_DELIVERY_ENABLED": bool(MAIL_DELIVERY_ENABLED),
            "SMTP_HOST": str(SMTP_HOST or ""),
            "SMTP_PORT": int(SMTP_PORT),
            "SMTP_USERNAME": SMTP_USERNAME,
            "SMTP_PASSWORD": SMTP_PASSWORD,
            "SMTP_FROM_EMAIL": str(SMTP_FROM_EMAIL or ""),
            "SMTP_FROM_NAME": str(SMTP_FROM_NAME or "WB Insight"),
            "SMTP_REPLY_TO_EMAIL": SMTP_REPLY_TO_EMAIL,
            "SMTP_STARTTLS": bool(SMTP_STARTTLS),
            "SMTP_TIMEOUT_SECONDS": float(SMTP_TIMEOUT_SECONDS),
            "source": str(source or ""),
            "updated_at": updated_at,
            "API_BASE_URL": str(API_BASE_URL or ""),
            "API_KEY_ID": API_KEY_ID,
            "API_TOKEN": API_TOKEN,
            "API_TIMEOUT_SECONDS": float(API_TIMEOUT_SECONDS),
            "diagnostic_code": diagnostic_code,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def __getattr__(self, name: str):
        # Совместимое чтение старых внутренних имён без хранения vendor-specific
        # полей в самом runtime-контракте.
        legacy_map = {
            "RUSENDER_API_BASE_URL": "API_BASE_URL",
            "RUSENDER_KEY_ID": "API_KEY_ID",
            "RUSENDER_API_TOKEN": "API_TOKEN",
            "RUSENDER_TIMEOUT_SECONDS": "API_TIMEOUT_SECONDS",
        }
        target = legacy_map.get(name)
        if target is None:
            raise AttributeError(name)
        return object.__getattribute__(self, target)

    @property
    def credentials_configured(self) -> bool:
        provider_class = _provider_class(self.MAIL_PROVIDER)
        capabilities = provider_class.capabilities
        if capabilities.transport_kind == "https_api":
            key_id_ready = bool(self.API_KEY_ID) or not provider_class.requires_key_id
            return bool(self.API_TOKEN and key_id_ready)
        if capabilities.transport_kind == "smtp":
            return bool(self.SMTP_USERNAME and self.SMTP_PASSWORD)
        return False

    @property
    def ready(self) -> bool:
        if not self.SMTP_FROM_EMAIL:
            return False
        provider_class = _provider_class(self.MAIL_PROVIDER)
        capabilities = provider_class.capabilities
        if capabilities.transport_kind == "smtp":
            if not self.SMTP_HOST:
                return False
            return bool(self.SMTP_USERNAME) == bool(self.SMTP_PASSWORD)
        if capabilities.transport_kind == "https_api":
            key_id_ready = bool(self.API_KEY_ID) or not provider_class.requires_key_id
            return bool(self.API_BASE_URL and self.API_TOKEN and key_id_ready)
        return False


def _secret_fingerprint(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    return "sha256:" + sha256(raw.encode("utf-8")).hexdigest()[:12]


def _secret_context(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in _SUPPORTED_PROVIDERS:
        raise ValueError("Неподдерживаемый почтовый транспорт")
    return f"mail-provider:{normalized}"


def _optional_bool(values: dict[str, Any], field: str) -> bool | None:
    if field not in values:
        return None
    value = values[field]
    if not isinstance(value, bool):
        raise ValueError(f"Поле {field} должно быть логическим значением")
    return value


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
    """Возвращает действующую конфигурацию почтового транспорта из базы."""
    if session is None:
        return None
    result = await session.execute(
        select(MailProviderConfig)
        .where(MailProviderConfig.provider.in_(_SUPPORTED_PROVIDERS))
        .order_by(
            MailProviderConfig.updated_at.desc(),
            MailProviderConfig.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def _environment_value(attribute_name: str | None, default=None):
    if not attribute_name:
        return default
    return getattr(lifecycle_config, attribute_name, default)


def _unconfigured_runtime(
    *,
    source: str,
    provider: str = "smtp",
    diagnostic_code: str | None = None,
) -> MailTransportRuntime:
    normalized = provider if provider in _SUPPORTED_PROVIDERS else "smtp"
    provider_class = _provider_class(normalized)
    capabilities = provider_class.capabilities
    uses_smtp = capabilities.transport_kind == "smtp"
    return MailTransportRuntime(
        MAIL_PROVIDER=normalized,
        MAIL_DELIVERY_ENABLED=False,
        SMTP_HOST="",
        SMTP_PORT=(587 if uses_smtp else int(provider_class.default_port)),
        SMTP_USERNAME=None,
        SMTP_PASSWORD=None,
        SMTP_FROM_EMAIL="",
        SMTP_FROM_NAME="WB Insight",
        SMTP_REPLY_TO_EMAIL=None,
        SMTP_STARTTLS=True,
        SMTP_TIMEOUT_SECONDS=10.0,
        API_BASE_URL=str(provider_class.default_api_base_url or ""),
        API_TIMEOUT_SECONDS=10.0,
        source=source,
        diagnostic_code=diagnostic_code,
    )


def _environment_runtime() -> MailTransportRuntime:
    provider = lifecycle_config.MAIL_PROVIDER
    provider_class = _provider_class(provider)
    capabilities = provider_class.capabilities
    uses_smtp = capabilities.transport_kind == "smtp"

    api_base_url = ""
    api_key_id = None
    api_token = None
    api_timeout = 10.0
    if capabilities.transport_kind == "https_api":
        api_base_url = str(
            _environment_value(
                provider_class.environment_api_base_url_attr,
                provider_class.default_api_base_url or "",
            )
            or provider_class.default_api_base_url
            or ""
        )
        api_key_id = str(
            _environment_value(provider_class.environment_key_id_attr, "") or ""
        ) or None
        api_token = str(
            _environment_value(provider_class.environment_api_token_attr, "") or ""
        ) or None
        api_timeout = float(
            _environment_value(provider_class.environment_timeout_attr, 10.0) or 10.0
        )

    return MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=(
            lifecycle_config.MAIL_DELIVERY_ENABLED
            if capabilities.marketing
            else False
        ),
        SMTP_HOST=lifecycle_config.SMTP_HOST if uses_smtp else "",
        SMTP_PORT=(
            int(lifecycle_config.SMTP_PORT)
            if uses_smtp
            else int(provider_class.default_port)
        ),
        SMTP_USERNAME=lifecycle_config.SMTP_USERNAME if uses_smtp else None,
        SMTP_PASSWORD=lifecycle_config.SMTP_PASSWORD if uses_smtp else None,
        SMTP_FROM_EMAIL=lifecycle_config.SMTP_FROM_EMAIL,
        SMTP_FROM_NAME=lifecycle_config.SMTP_FROM_NAME,
        SMTP_REPLY_TO_EMAIL=(
            lifecycle_config.SMTP_REPLY_TO_EMAIL if capabilities.reply_to else None
        ),
        SMTP_STARTTLS=(bool(lifecycle_config.SMTP_STARTTLS) if uses_smtp else True),
        SMTP_TIMEOUT_SECONDS=float(lifecycle_config.SMTP_TIMEOUT_SECONDS),
        API_BASE_URL=api_base_url,
        API_KEY_ID=api_key_id,
        API_TOKEN=api_token,
        API_TIMEOUT_SECONDS=api_timeout,
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
            lifecycle_config.MAIL_DELIVERY_ENABLED
            and not mail_provider_capabilities(runtime.MAIL_PROVIDER).marketing
        ):
            return _unconfigured_runtime(
                source="unconfigured",
                provider=runtime.MAIL_PROVIDER,
                diagnostic_code="environment_fallback_invalid",
            )
        try:
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
    provider_class = _provider_class(provider)
    capabilities = provider_class.capabilities
    uses_smtp = capabilities.transport_kind == "smtp"

    runtime = MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=(bool(row.enabled) if capabilities.marketing else False),
        SMTP_HOST=str(row.host or "") if uses_smtp else "",
        SMTP_PORT=int(row.port or provider_class.default_port),
        SMTP_USERNAME=(str(secrets.get("username") or "") or None) if uses_smtp else None,
        SMTP_PASSWORD=(str(secrets.get("password") or "") or None) if uses_smtp else None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=(
            (str(row.reply_to_email or "") or None)
            if capabilities.reply_to
            else None
        ),
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        API_BASE_URL=(
            str(row.host or provider_class.default_api_base_url or "")
            if capabilities.transport_kind == "https_api"
            else ""
        ),
        API_KEY_ID=(
            str(secrets.get("key_id") or "") or None
            if capabilities.transport_kind == "https_api"
            else None
        ),
        API_TOKEN=(
            str(secrets.get("api_token") or "") or None
            if capabilities.transport_kind == "https_api"
            else None
        ),
        API_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )
    if runtime.ready:
        return runtime
    return MailTransportRuntime(
        **{
            **runtime.__dict__,
            "diagnostic_code": "database_transport_incomplete",
        }
    )


async def mail_transport_payload(session: AsyncSession) -> dict[str, Any]:
    runtime = await get_mail_transport_runtime(session)
    provider = mail_provider_for_runtime(runtime)
    capabilities = provider.capabilities

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

    return {
        "provider": runtime.MAIL_PROVIDER,
        "provider_label": provider.display_name,
        "transport_kind": capabilities.transport_kind,
        "capabilities": capabilities.as_payload(),
        "available_providers": mail_provider_catalog(),
        "enabled": runtime.MAIL_DELIVERY_ENABLED,
        "ready": runtime.ready,
        "marketing_ready": bool(
            runtime.ready
            and runtime.MAIL_DELIVERY_ENABLED
            and unsubscribe_configured
            and capabilities.marketing
        ),
        "marketing_transport_supported": capabilities.marketing,
        "unsubscribe_configured": unsubscribe_configured,
        "source": runtime.source,
        "host": runtime.SMTP_HOST,
        "port": runtime.SMTP_PORT,
        "api_base_url": runtime.API_BASE_URL,
        "key_id": runtime.API_KEY_ID,
        "from_email": runtime.SMTP_FROM_EMAIL,
        "from_name": runtime.SMTP_FROM_NAME,
        "reply_to_email": runtime.SMTP_REPLY_TO_EMAIL,
        "starttls": runtime.SMTP_STARTTLS,
        "timeout_seconds": (
            runtime.API_TIMEOUT_SECONDS
            if capabilities.transport_kind == "https_api"
            else runtime.SMTP_TIMEOUT_SECONDS
        ),
        "credentials_configured": runtime.credentials_configured,
        "credential_fingerprint": (
            _secret_fingerprint(runtime.API_TOKEN)
            if capabilities.transport_kind == "https_api"
            else None
        ),
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
                capabilities.provider_managed_tls
                or (
                    capabilities.transport_kind == "smtp"
                    and runtime.SMTP_STARTTLS
                )
            ),
            "sender_identity": bool(runtime.SMTP_FROM_EMAIL and runtime.SMTP_FROM_NAME),
            "reply_to_configured": bool(
                capabilities.reply_to and runtime.SMTP_REPLY_TO_EMAIL
            ),
            "one_click_unsubscribe": bool(
                unsubscribe_configured and capabilities.one_click_unsubscribe
            ),
            "spf": "external",
            "dkim": "external",
            "dmarc": "external",
            "ptr": "provider" if capabilities.provider_managed_ptr else "external",
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
        supported = ", ".join(
            _provider_class(code).display_name
            for code in sorted(_SUPPORTED_PROVIDERS)
        )
        raise ValueError(f"Поддерживаемые почтовые транспорты: {supported}")

    provider_class = _provider_class(provider)
    capabilities = provider_class.capabilities
    uses_smtp = capabilities.transport_kind == "smtp"

    enabled_value = _optional_bool(values, "enabled")
    clear_credentials = _optional_bool(values, "clear_credentials")
    starttls_value = _optional_bool(values, "starttls")

    row = await get_mail_provider_config(session)
    existing: dict[str, Any] = {}
    if row is None:
        row = MailProviderConfig(provider=provider)
        row.port = int(provider_class.default_port)
        session.add(row)
        await session.flush()
    elif str(row.provider).lower() == provider:
        existing = _read_secrets(row)
    else:
        row.provider = provider
        row.encrypted_secrets = None
        row.host = None
        row.port = int(provider_class.default_port)
        row.starttls = not uses_smtp
        existing = {}

    if not capabilities.marketing:
        row.enabled = False
    elif enabled_value is not None:
        row.enabled = enabled_value

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

    if clear_credentials is True:
        existing = {}

    if uses_smtp:
        if "host" in values:
            row.host = str(values.get("host") or "").strip() or None
        if "port" in values:
            port = int(values["port"])
            if port <= 0 or port > 65535:
                raise ValueError("SMTP port должен быть от 1 до 65535")
            row.port = port
        if starttls_value is not None:
            row.starttls = starttls_value

        if clear_credentials is not True:
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
            raise ValueError("SMTP логин и пароль должны быть настроены вместе")
    elif capabilities.transport_kind == "https_api":
        api_base_url = str(provider_class.default_api_base_url or "").strip()
        if not api_base_url:
            raise ValueError("HTTPS API провайдера не содержит доверенного endpoint")
        row.host = api_base_url
        row.port = int(provider_class.default_port)
        row.starttls = True

        key_id = str(values.get("key_id") or existing.get("key_id") or "").strip()
        if key_id and provider_class.key_id_numeric and not key_id.isdigit():
            raise ValueError("ID ключа почтового провайдера должен быть числом")
        if key_id:
            existing["key_id"] = key_id
        else:
            existing.pop("key_id", None)

        if clear_credentials is not True and "api_token" in values:
            api_token = str(values.get("api_token") or "").strip()
            if api_token:
                existing["api_token"] = api_token
        if clear_credentials is True:
            existing.pop("api_token", None)
    else:
        raise ValueError("Тип конфигурации почтового провайдера не поддерживается")

    row.encrypted_secrets = (
        encrypt_secret_payload(existing, context=_secret_context(provider))
        if existing
        else None
    )
    row.updated_by = actor_id

    runtime = MailTransportRuntime(
        MAIL_PROVIDER=provider,
        MAIL_DELIVERY_ENABLED=bool(row.enabled) if capabilities.marketing else False,
        SMTP_HOST=str(row.host or "") if uses_smtp else "",
        SMTP_PORT=int(row.port or provider_class.default_port),
        SMTP_USERNAME=(str(existing.get("username") or "") or None) if uses_smtp else None,
        SMTP_PASSWORD=(str(existing.get("password") or "") or None) if uses_smtp else None,
        SMTP_FROM_EMAIL=str(row.from_email or ""),
        SMTP_FROM_NAME=str(row.from_name or "WB Insight"),
        SMTP_REPLY_TO_EMAIL=(
            (str(row.reply_to_email or "") or None)
            if capabilities.reply_to
            else None
        ),
        SMTP_STARTTLS=bool(row.starttls),
        SMTP_TIMEOUT_SECONDS=float(row.timeout_seconds),
        API_BASE_URL=(
            str(row.host or "")
            if capabilities.transport_kind == "https_api"
            else ""
        ),
        API_KEY_ID=(
            str(existing.get("key_id") or "") or None
            if capabilities.transport_kind == "https_api"
            else None
        ),
        API_TOKEN=(
            str(existing.get("api_token") or "") or None
            if capabilities.transport_kind == "https_api"
            else None
        ),
        API_TIMEOUT_SECONDS=float(row.timeout_seconds),
        source="database",
    )

    if not runtime.ready:
        if capabilities.transport_kind == "https_api":
            required = "API-токен и email отправителя"
            if provider_class.requires_key_id:
                required = "ID ключа, API-токен и email отправителя"
            raise ValueError(f"Заполните {required} почтового провайдера")
        raise ValueError(
            "Заполните SMTP host, email отправителя и согласованную пару логин/пароль"
        )

    if config.IS_PRODUCTION and uses_smtp and not runtime.SMTP_STARTTLS:
        raise ValueError("В production SMTP должен использовать STARTTLS")
    if (
        config.IS_PRODUCTION
        and capabilities.transport_kind == "https_api"
        and not runtime.API_BASE_URL.startswith("https://")
    ):
        raise ValueError("В production почтовый API должен использовать HTTPS")

    await session.flush()
    return row


def mail_provider_for_runtime(runtime: MailTransportRuntime):
    provider_class = _provider_class(runtime.MAIL_PROVIDER)
    return provider_class(runtime)


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
        subject="WB Insight — проверка доставки",
        body=(
            "Проверка доставки WB Insight выполнена.\n\n"
            "Это служебное письмо было отправлено по запросу администратора "
            "из Панели управления. Никаких действий выполнять не требуется."
        ),
        html_body=(
            '<!doctype html><html><body style="font-family:Arial,sans-serif;'
            'background:#f5f6fb;padding:24px;color:#182033;">'
            '<div style="max-width:620px;margin:auto;background:#fff;padding:28px;'
            'border-radius:14px;"><h2 style="margin-top:0;">Проверка доставки WB Insight</h2>'
            '<p>Транзакционный почтовый транспорт принял тестовое письмо.</p>'
            '<p>Это служебная проверка по запросу администратора. '
            'Никаких действий выполнять не требуется.</p>'
            '</div></body></html>'
        ),
        preview_title="Проверка транзакционной доставки WB Insight",
        headers={
            "X-WB-Message-Type": "gateway-test",
        },
        idempotency_key=f"gateway-test:{uuid4()}",
    )
    return receipt.provider_message_id or ""
