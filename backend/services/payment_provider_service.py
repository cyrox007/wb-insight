from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment_provider_config import PaymentProviderConfig
from settings import config
from utils.secret_crypto import decrypt_secret_payload, encrypt_secret_payload


PAYMENT_MODES = {"test", "live"}
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "sber": {
        "name": "Сбер",
        "adapter_available": True,
        "supports_test": True,
        "supports_live": True,
        "description": "Интернет-эквайринг Сбера",
    },
    "fake": {
        "name": "Тестовая оплата",
        "adapter_available": True,
        "supports_test": True,
        "supports_live": False,
        "description": "Локальный провайдер для тестирования сценариев оплаты",
    },
    "yookassa": {
        "name": "ЮKassa",
        "adapter_available": False,
        "supports_test": True,
        "supports_live": True,
        "description": "Адаптер зарезервирован и будет подключён отдельно",
    },
}
SBER_TEST_API_BASE_URL = "https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1"


@dataclass(frozen=True)
class PaymentProviderRuntime:
    provider: str
    mode: str
    enabled: bool
    is_default: bool
    ready: bool
    source: str
    api_base_url: str | None = None
    return_url: str | None = None
    fail_url: str | None = None
    currency_code: str = "643"
    timeout_seconds: float = 10.0
    username: str | None = None
    password: str | None = None
    options: dict[str, Any] | None = None


def _secret_context(provider: str, mode: str) -> str:
    return f"payment-provider:{provider}:{mode}"


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    if not value or len(value) > 32 or not all(ch.isalnum() or ch in {"_", "-"} for ch in value):
        raise ValueError("Некорректный код платёжного провайдера")
    return value


def _normalize_mode(mode: str) -> str:
    value = mode.strip().lower()
    if value not in PAYMENT_MODES:
        raise ValueError("Режим платёжного провайдера должен быть test или live")
    return value


def _mask_identifier(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "•" * len(value)
    return f"{value[:2]}{'•' * max(4, len(value) - 4)}{value[-2:]}"


def _sber_environment_values() -> dict[str, Any]:
    return {
        "api_base_url": config.SBER_API_BASE_URL,
        "return_url": config.SBER_RETURN_URL,
        "fail_url": config.SBER_FAIL_URL,
        "currency_code": config.SBER_CURRENCY_CODE,
        "timeout_seconds": config.SBER_HTTP_TIMEOUT_SECONDS,
        "username": config.SBER_USERNAME,
        "password": config.SBER_PASSWORD,
    }


def _read_secrets(row: PaymentProviderConfig | None) -> dict[str, Any]:
    if row is None or not row.encrypted_secrets:
        return {}
    return decrypt_secret_payload(
        row.encrypted_secrets,
        context=_secret_context(row.provider, row.mode),
    )


def _effective_runtime(row: PaymentProviderConfig | None, provider: str, mode: str) -> PaymentProviderRuntime:
    catalog = PROVIDER_CATALOG.get(provider, {})
    adapter_available = bool(catalog.get("adapter_available", False))
    secrets = _read_secrets(row)

    if provider == "sber":
        # The legacy ENV settings remain a backwards-compatible live fallback.
        # Test configuration is isolated and never inherits live credentials.
        env = _sber_environment_values() if mode == "live" else {
            "api_base_url": SBER_TEST_API_BASE_URL,
            "return_url": None,
            "fail_url": None,
            "currency_code": "643",
            "timeout_seconds": config.SBER_HTTP_TIMEOUT_SECONDS,
            "username": None,
            "password": None,
        }
        api_base_url = row.api_base_url if row and row.api_base_url else env["api_base_url"]
        return_url = row.return_url if row and row.return_url else env["return_url"]
        fail_url = row.fail_url if row and row.fail_url else env["fail_url"]
        currency_code = row.currency_code if row and row.currency_code else env["currency_code"]
        timeout_seconds = float(row.timeout_seconds if row else env["timeout_seconds"])
        username = str(secrets.get("username") or env["username"] or "") or None
        password = str(secrets.get("password") or env["password"] or "") or None
        enabled = bool(row.enabled) if row else bool(config.SBER_ACQUIRING_ENABLED and mode == "live")
        is_default = bool(row.is_default) if row else bool(config.SBER_ACQUIRING_ENABLED and mode == "live")
        source = "database" if row else ("environment" if config.SBER_ACQUIRING_ENABLED and mode == "live" else "unconfigured")
        ready = bool(adapter_available and api_base_url and return_url and fail_url and username and password)
        return PaymentProviderRuntime(
            provider=provider,
            mode=mode,
            enabled=enabled,
            is_default=is_default,
            ready=ready,
            source=source,
            api_base_url=api_base_url,
            return_url=return_url,
            fail_url=fail_url,
            currency_code=currency_code or "643",
            timeout_seconds=timeout_seconds,
            username=username,
            password=password,
            options=dict(row.options or {}) if row else {},
        )

    if provider == "fake":
        enabled = bool(row.enabled) if row else bool(config.ALLOW_FAKE_BILLING and mode == "test")
        source = "database" if row else ("environment" if enabled else "unconfigured")
        return PaymentProviderRuntime(
            provider=provider,
            mode=mode,
            enabled=enabled,
            is_default=bool(row.is_default) if row else enabled,
            ready=bool(adapter_available and mode == "test" and not config.IS_PRODUCTION),
            source=source,
            options=dict(row.options or {}) if row else {},
        )

    return PaymentProviderRuntime(
        provider=provider,
        mode=mode,
        enabled=bool(row.enabled) if row else False,
        is_default=bool(row.is_default) if row else False,
        ready=False,
        source="database" if row else "unconfigured",
        api_base_url=row.api_base_url if row else None,
        return_url=row.return_url if row else None,
        fail_url=row.fail_url if row else None,
        currency_code=row.currency_code if row else "643",
        timeout_seconds=float(row.timeout_seconds) if row else 10.0,
        username=str(secrets.get("username") or "") or None,
        password=str(secrets.get("password") or "") or None,
        options=dict(row.options or {}) if row else {},
    )


async def get_provider_config(
    session: AsyncSession | None,
    provider: str,
    mode: str,
) -> PaymentProviderConfig | None:
    provider = _normalize_provider(provider)
    mode = _normalize_mode(mode)
    if session is None:
        return None
    result = await session.execute(
        select(PaymentProviderConfig).where(
            PaymentProviderConfig.provider == provider,
            PaymentProviderConfig.mode == mode,
        )
    )
    return result.scalar_one_or_none()


async def get_provider_runtime(
    session: AsyncSession | None,
    provider: str,
    mode: str,
) -> PaymentProviderRuntime:
    provider = _normalize_provider(provider)
    mode = _normalize_mode(mode)
    row = await get_provider_config(session, provider, mode)
    return _effective_runtime(row, provider, mode)


async def resolve_checkout_provider(session: AsyncSession | None) -> PaymentProviderRuntime | None:
    allowed_modes = {"live"} if config.IS_PRODUCTION else PAYMENT_MODES
    if session is not None:
        result = await session.execute(
            select(PaymentProviderConfig)
            .where(
                PaymentProviderConfig.enabled.is_(True),
                PaymentProviderConfig.is_default.is_(True),
                PaymentProviderConfig.mode.in_(allowed_modes),
            )
            .order_by(PaymentProviderConfig.updated_at.desc())
        )
        for row in result.scalars().all():
            runtime = _effective_runtime(row, row.provider, row.mode)
            if runtime.ready:
                return runtime

    if config.SBER_ACQUIRING_ENABLED:
        runtime = _effective_runtime(None, "sber", "live")
        if runtime.ready:
            return runtime
    if not config.IS_PRODUCTION and config.ALLOW_FAKE_BILLING:
        runtime = _effective_runtime(None, "fake", "test")
        if runtime.ready:
            return runtime
    return None


async def list_provider_configs(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(PaymentProviderConfig))
    rows = {(row.provider, row.mode): row for row in result.scalars().all()}
    pairs = set(rows)
    pairs.update({("sber", "live"), ("sber", "test"), ("fake", "test"), ("yookassa", "live"), ("yookassa", "test")})

    payload: list[dict[str, Any]] = []
    for provider, mode in sorted(pairs):
        row = rows.get((provider, mode))
        runtime = _effective_runtime(row, provider, mode)
        catalog = PROVIDER_CATALOG.get(provider, {})
        if mode == "test" and catalog and not catalog.get("supports_test", False):
            continue
        if mode == "live" and catalog and not catalog.get("supports_live", False):
            continue
        payload.append(
            {
                "provider": provider,
                "name": catalog.get("name", provider),
                "description": catalog.get("description", "Платёжный провайдер"),
                "mode": mode,
                "enabled": runtime.enabled,
                "is_default": runtime.is_default,
                "ready": runtime.ready,
                "adapter_available": bool(catalog.get("adapter_available", False)),
                "source": runtime.source,
                "api_base_url": runtime.api_base_url,
                "return_url": runtime.return_url,
                "fail_url": runtime.fail_url,
                "currency_code": runtime.currency_code,
                "timeout_seconds": runtime.timeout_seconds,
                "credentials_configured": bool(runtime.username and runtime.password),
                "credential_hint": _mask_identifier(runtime.username),
                "options": runtime.options or {},
                "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            }
        )
    return payload


async def upsert_provider_config(
    session: AsyncSession,
    *,
    provider: str,
    mode: str,
    actor_id: UUID,
    values: dict[str, Any],
) -> PaymentProviderConfig:
    provider = _normalize_provider(provider)
    mode = _normalize_mode(mode)
    catalog = PROVIDER_CATALOG.get(provider)
    if not catalog:
        raise ValueError("Провайдер ещё не зарегистрирован в приложении")
    if mode == "live" and not catalog.get("supports_live", False):
        raise ValueError("Этот провайдер не поддерживает live-режим")
    if mode == "test" and not catalog.get("supports_test", False):
        raise ValueError("Этот провайдер не поддерживает test-режим")

    row = await get_provider_config(session, provider, mode)
    if row is None:
        row = PaymentProviderConfig(provider=provider, mode=mode)
        session.add(row)
        await session.flush()

    for field in ("api_base_url", "return_url", "fail_url", "currency_code"):
        if field in values:
            raw = values.get(field)
            setattr(row, field, str(raw).strip() if raw not in (None, "") else None)
    if "timeout_seconds" in values:
        timeout = float(values["timeout_seconds"])
        if timeout <= 0 or timeout > 120:
            raise ValueError("timeout_seconds должен быть от 0 до 120 секунд")
        row.timeout_seconds = timeout
    if "options" in values:
        if values["options"] is not None and not isinstance(values["options"], dict):
            raise ValueError("options должен быть объектом")
        row.options = values["options"] or {}

    existing_secrets = _read_secrets(row)
    if values.get("clear_secrets") is True:
        existing_secrets = {}
    secrets = dict(existing_secrets)
    for field in ("username", "password"):
        if field in values and values[field] not in (None, ""):
            secrets[field] = str(values[field]).strip()
    row.encrypted_secrets = (
        encrypt_secret_payload(secrets, context=_secret_context(provider, mode))
        if secrets
        else None
    )

    requested_enabled = bool(values.get("enabled", row.enabled))
    requested_default = bool(values.get("is_default", row.is_default))
    if provider == "fake" and mode != "test" and requested_enabled:
        raise ValueError("Fake-провайдер разрешён только в test-режиме")
    if provider == "fake" and config.IS_PRODUCTION and requested_enabled:
        raise ValueError("Fake-провайдер нельзя включать в production")
    if config.IS_PRODUCTION and mode != "live" and requested_default:
        raise ValueError("В production провайдер по умолчанию должен работать в live-режиме")
    if requested_enabled and not catalog.get("adapter_available", False):
        raise ValueError("Адаптер этого провайдера ещё не подключён")

    row.enabled = requested_enabled
    row.is_default = requested_default
    row.updated_by = actor_id
    await session.flush()

    runtime = _effective_runtime(row, provider, mode)
    if row.enabled and not runtime.ready:
        raise ValueError("Провайдер нельзя включить: конфигурация не готова")
    if row.is_default and not row.enabled:
        raise ValueError("Провайдер по умолчанию должен быть включён")

    if row.is_default:
        await session.execute(
            update(PaymentProviderConfig)
            .where(PaymentProviderConfig.id != row.id)
            .values(is_default=False)
        )
    await session.flush()
    return row
