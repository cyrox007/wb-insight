from dataclasses import dataclass
from math import isfinite
import re
from typing import Any
from urllib.parse import urlparse, urlunparse
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
SBER_GATEWAY_PATH = "/ecomm/gw/partner/api/v1"
SBER_SANDBOX_HOSTS = frozenset(
    {
        "ecomift.sberbank.ru",
        "ecomtest.sberbank.ru",
    }
)


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


def _optional_bool(values: dict[str, Any], field: str) -> bool | None:
    if field not in values:
        return None
    value = values[field]
    if not isinstance(value, bool):
        raise ValueError(f"Поле {field} должно быть логическим значением")
    return value


def _normalize_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Таймаут платёжного провайдера должен быть числом") from exc
    if not isfinite(timeout) or timeout <= 0 or timeout > 120:
        raise ValueError("Таймаут платёжного провайдера должен быть от 0 до 120 секунд")
    return timeout


def _normalize_currency_code(value: Any) -> str:
    currency = str(value or "").strip()
    if re.fullmatch(r"\d{3}", currency) is None:
        raise ValueError("Код валюты должен состоять из трёх цифр")
    return currency


def _normalize_sber_gateway_url(value: Any, mode: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL платёжного шлюза Сбера имеет некорректный формат") from exc

    hostname = (parsed.hostname or "").rstrip(".").lower()
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in {None, 443}
        or path != SBER_GATEWAY_PATH
    ):
        raise ValueError(
            "URL платёжного шлюза Сбера должен быть HTTPS без credentials/query/fragment "
            "и использовать маршрут /ecomm/gw/partner/api/v1"
        )

    if mode == "test":
        if hostname not in SBER_SANDBOX_HOSTS:
            raise ValueError("Test-режим Сбера должен использовать sandbox-шлюз Сбера")
    elif (
        hostname in SBER_SANDBOX_HOSTS
        or not (hostname == "sberbank.ru" or hostname.endswith(".sberbank.ru"))
    ):
        raise ValueError(
            "Live-режим Сбера должен использовать промышленный шлюз в домене sberbank.ru"
        )

    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunparse(("https", netloc, SBER_GATEWAY_PATH, "", "", ""))


def _normalize_redirect_url(value: Any, field: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = urlparse(raw)
        parsed.port
    except ValueError as exc:
        raise ValueError(f"Поле {field} содержит некорректный URL") from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError(
            f"Поле {field} должно быть абсолютным HTTP(S) URL без credentials и fragment"
        )
    if config.IS_PRODUCTION and parsed.scheme.lower() != "https":
        raise ValueError(f"В production поле {field} должно использовать HTTPS")
    return raw


def _sber_runtime_urls_safe(
    api_base_url: str | None,
    return_url: str | None,
    fail_url: str | None,
    mode: str,
) -> bool:
    try:
        _normalize_sber_gateway_url(api_base_url, mode)
        _normalize_redirect_url(return_url, "return_url")
        _normalize_redirect_url(fail_url, "fail_url")
    except ValueError:
        return False
    return bool(return_url and fail_url)


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
        # Устаревшая ENV-конфигурация остаётся совместимым fallback для live.
        # Test-конфигурация изолирована и никогда не наследует live credentials.
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
        gateway_safe = _sber_runtime_urls_safe(
            api_base_url,
            return_url,
            fail_url,
            mode,
        )
        currency_safe = re.fullmatch(r"\d{3}", str(currency_code or "")) is not None
        timeout_safe = isfinite(timeout_seconds) and 0 < timeout_seconds <= 120
        ready = bool(
            adapter_available
            and gateway_safe
            and currency_safe
            and timeout_safe
            and username
            and password
        )
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

    enabled_value = _optional_bool(values, "enabled")
    default_value = _optional_bool(values, "is_default")
    clear_secrets = _optional_bool(values, "clear_secrets")

    normalized_fields: dict[str, Any] = {}
    if "api_base_url" in values:
        raw_api_url = values.get("api_base_url")
        if provider == "sber" and raw_api_url not in (None, ""):
            normalized_fields["api_base_url"] = _normalize_sber_gateway_url(
                raw_api_url,
                mode,
            )
        else:
            normalized_fields["api_base_url"] = (
                str(raw_api_url).strip() if raw_api_url not in (None, "") else None
            )

    for field in ("return_url", "fail_url"):
        if field not in values:
            continue
        raw_url = values.get(field)
        normalized_fields[field] = (
            _normalize_redirect_url(raw_url, field)
            if provider == "sber"
            else (str(raw_url).strip() if raw_url not in (None, "") else None)
        )

    if "currency_code" in values:
        normalized_fields["currency_code"] = (
            _normalize_currency_code(values["currency_code"])
            if provider == "sber"
            else str(values["currency_code"] or "").strip()
        )

    timeout_value = (
        _normalize_timeout(values["timeout_seconds"])
        if "timeout_seconds" in values
        else None
    )
    options_value = None
    if "options" in values:
        if values["options"] is not None and not isinstance(values["options"], dict):
            raise ValueError("options должен быть объектом")
        options_value = values["options"] or {}

    async with session.begin_nested():
        row = await get_provider_config(session, provider, mode)
        if row is None:
            row = PaymentProviderConfig(provider=provider, mode=mode)
            session.add(row)

        for field, value in normalized_fields.items():
            setattr(row, field, value)
        if timeout_value is not None:
            row.timeout_seconds = timeout_value
        if "options" in values:
            row.options = options_value

        existing_secrets = _read_secrets(row)
        if clear_secrets is True:
            existing_secrets = {}
        secrets = dict(existing_secrets)
        for field in ("username", "password"):
            if field in values and values[field] not in (None, ""):
                secrets[field] = str(values[field]).strip()
        row.encrypted_secrets = (
            encrypt_secret_payload(
                secrets,
                context=_secret_context(provider, mode),
            )
            if secrets
            else None
        )

        requested_enabled = row.enabled if enabled_value is None else enabled_value
        requested_default = row.is_default if default_value is None else default_value
        if provider == "fake" and mode != "test" and requested_enabled:
            raise ValueError("Fake-провайдер разрешён только в test-режиме")
        if provider == "fake" and config.IS_PRODUCTION and requested_enabled:
            raise ValueError("Fake-провайдер нельзя включать в production")
        if config.IS_PRODUCTION and mode != "live" and requested_default:
            raise ValueError(
                "В production провайдер по умолчанию должен работать в live-режиме"
            )
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
