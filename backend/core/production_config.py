"""Fail-closed validation for production-only configuration.

Development keeps convenient local defaults. Production must not start with
sample credentials, weak well-known defaults, malformed encryption material or
HTTP-only public endpoints copied from a development setup.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


_WEAK_SECRET_VALUES = {
    "admin",
    "changeme",
    "change-me",
    "default",
    "password",
    "postgres",
    "secret",
}


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return (
        not normalized
        or "replace-with-" in normalized
        or normalized in _WEAK_SECRET_VALUES
    )


def _require_secret(name: str, value: str | None, *, min_length: int | None = None) -> str:
    if _looks_like_placeholder(value):
        raise RuntimeError(f"{name} must be replaced with a production value")
    assert value is not None
    if min_length is not None and len(value) < min_length:
        raise RuntimeError(f"{name} must be at least {min_length} characters in production")
    return value


def _require_https(name: str, value: str | None) -> None:
    if not value or not value.strip().lower().startswith("https://"):
        raise RuntimeError(f"{name} must use https:// in production")


def validate_production_config(config) -> None:
    """Validate values that are dangerous to leave permissive in production."""
    if not config.IS_PRODUCTION:
        return

    if config.DEBUG:
        raise RuntimeError("DEBUG must be false when APP_ENV=production")

    if config.SERVER_HTTP_PROTOCOL.strip().lower() != "https://":
        raise RuntimeError("SERVER_HTTP_PROTOCOL must be https:// in production")

    for origin in config.get_allowed_origins:
        _require_https("ALLOWED_ORIGINS", origin)

    _require_secret("DB_PASSWORD", config.DB_PASSWORD, min_length=16)
    _require_secret("JWT_SECRET_KEY", config.SECRET_KEY, min_length=32)
    encryption_key = _require_secret("API_TOKEN_ENCRYPTION_KEY", config.ENCRYPTION_KEY)
    try:
        Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "API_TOKEN_ENCRYPTION_KEY must be a valid Fernet key in production"
        ) from exc

    if _looks_like_placeholder(config.WB_SERVICE_ID):
        raise RuntimeError("WB_SERVICE_ID must be replaced with a production value")
    _require_secret("WB_SERVICE_SECRET", config.WB_SERVICE_SECRET)

    if config.SBER_ACQUIRING_ENABLED:
        if _looks_like_placeholder(config.SBER_USERNAME):
            raise RuntimeError("SBER_USERNAME must be replaced with a production value")
        _require_secret("SBER_PASSWORD", config.SBER_PASSWORD)
        _require_https("SBER_API_BASE_URL", config.SBER_API_BASE_URL)
        _require_https("SBER_RETURN_URL", config.SBER_RETURN_URL)
        _require_https("SBER_FAIL_URL", config.SBER_FAIL_URL)
