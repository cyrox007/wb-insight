from types import SimpleNamespace

import pytest

from core.lifecycle_config import LifecycleConfig
from core.production_config import validate_production_config


VALID_FERNET_KEY = "2A3k6qmH-9j-jppiuX-2xFvrNEeLp3aKjbIy2Verwxc="


def _production_config(**overrides):
    values = {
        "IS_PRODUCTION": True,
        "DEBUG": False,
        "SERVER_HTTP_PROTOCOL": "https://",
        "BASE_URL": "https://app.wbinsight.ru",
        "get_allowed_origins": ["https://app.wbinsight.ru"],
        "DB_PASSWORD": "db-production-password-2026",
        "SECRET_KEY": "jwt-production-secret-key-with-more-than-32-chars",
        "LEGAL_EVIDENCE_HMAC_KEY": "legal-evidence-production-key-over-32-chars",
        "ENCRYPTION_KEY": VALID_FERNET_KEY,
        "WB_SERVICE_ID": "wb-service-12345",
        "WB_SERVICE_SECRET": "wb-service-secret-production-value",
        "SBER_ACQUIRING_ENABLED": False,
        "SBER_USERNAME": "merchant-production-user",
        "SBER_PASSWORD": "merchant-production-password",
        "SBER_API_BASE_URL": "https://securepayments.sberbank.ru/payment/rest",
        "SBER_RETURN_URL": "https://app.wbinsight.ru/billing/success",
        "SBER_FAIL_URL": "https://app.wbinsight.ru/billing/fail",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _lifecycle_config(**overrides):
    config = LifecycleConfig()
    values = {
        "PASSWORD_RESET_ENABLED": True,
        "PASSWORD_RESET_BASE_URL": "https://app.wbinsight.ru/reset-password",
        "PASSWORD_RESET_TOKEN_TTL_MINUTES": 30,
        "MAIL_CONFIG_SOURCE": "environment",
        "MAIL_PROVIDER": "smtp",
        "SMTP_HOST": "smtp.mail-provider.ru",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "wbinsight-mailer",
        "SMTP_PASSWORD": "provider-generated-mail-secret",
        "SMTP_FROM_EMAIL": "no-reply@wbinsight.ru",
        "SMTP_STARTTLS": True,
        "SMTP_TIMEOUT_SECONDS": 10.0,
        "ACCOUNT_DEACTIVATION_RETENTION_DAYS": 90,
    }
    values.update(overrides)
    for name, value in values.items():
        setattr(config, name, value)
    return config


def test_development_config_keeps_local_defaults_available():
    validate_production_config(SimpleNamespace(IS_PRODUCTION=False))


def test_valid_production_config_passes_preflight():
    validate_production_config(_production_config())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"DEBUG": True}, "DEBUG"),
        ({"SERVER_HTTP_PROTOCOL": "http://"}, "SERVER_HTTP_PROTOCOL"),
        ({"BASE_URL": "https://app.example.com"}, "BASE_URL"),
        ({"get_allowed_origins": ["http://app.wbinsight.ru"]}, "ALLOWED_ORIGINS"),
        ({"DB_PASSWORD": "postgres"}, "DB_PASSWORD"),
        ({"DB_PASSWORD": "too-short"}, "DB_PASSWORD"),
        ({"SECRET_KEY": "replace-with-long-random-jwt-secret"}, "JWT_SECRET_KEY"),
        ({"SECRET_KEY": "too-short"}, "JWT_SECRET_KEY"),
        ({"LEGAL_EVIDENCE_HMAC_KEY": "replace-with-independent-long-random-secret"}, "LEGAL_EVIDENCE_HMAC_KEY"),
        ({"LEGAL_EVIDENCE_HMAC_KEY": "too-short"}, "LEGAL_EVIDENCE_HMAC_KEY"),
        ({"ENCRYPTION_KEY": "not-a-fernet-key"}, "API_TOKEN_ENCRYPTION_KEY"),
        ({"WB_SERVICE_ID": "replace-with-wb-service-id"}, "WB_SERVICE_ID"),
        ({"WB_SERVICE_SECRET": "replace-with-wb-service-secret"}, "WB_SERVICE_SECRET"),
    ],
)
def test_production_preflight_rejects_unsafe_core_values(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        validate_production_config(_production_config(**overrides))


def test_sber_disabled_does_not_require_provider_credentials():
    validate_production_config(
        _production_config(
            SBER_ACQUIRING_ENABLED=False,
            SBER_USERNAME="replace-with-merchant-username",
            SBER_PASSWORD="replace-with-merchant-password",
            SBER_API_BASE_URL="https://replace-with-production-sber-gateway",
            SBER_RETURN_URL="https://app.example.com/billing/success",
            SBER_FAIL_URL="https://app.example.com/billing/fail",
        )
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SBER_USERNAME": "replace-with-merchant-username"}, "SBER_USERNAME"),
        ({"SBER_PASSWORD": "replace-with-merchant-password"}, "SBER_PASSWORD"),
        ({"SBER_API_BASE_URL": "https://replace-with-production-sber-gateway"}, "SBER_API_BASE_URL"),
        ({"SBER_RETURN_URL": "https://app.example.com/billing/success"}, "SBER_RETURN_URL"),
        ({"SBER_FAIL_URL": "http://app.wbinsight.ru/billing/fail"}, "SBER_FAIL_URL"),
    ],
)
def test_enabled_sber_rejects_placeholder_or_insecure_values(overrides, message):
    config = _production_config(SBER_ACQUIRING_ENABLED=True)
    for name, value in overrides.items():
        setattr(config, name, value)
    with pytest.raises(RuntimeError, match=message):
        validate_production_config(config)


def test_valid_production_password_recovery_config_passes():
    _lifecycle_config().validate(production=True)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"PASSWORD_RESET_BASE_URL": "https://app.example.com/reset-password"}, "PASSWORD_RESET_BASE_URL"),
        ({"PASSWORD_RESET_BASE_URL": "http://app.wbinsight.ru/reset-password"}, "PASSWORD_RESET_BASE_URL"),
        ({"SMTP_HOST": "smtp.example.com"}, "SMTP_HOST"),
        ({"SMTP_FROM_EMAIL": "no-reply@example.com"}, "SMTP_FROM_EMAIL"),
        ({"SMTP_STARTTLS": False}, "SMTP_STARTTLS"),
        ({"SMTP_USERNAME": "replace-with-smtp-user"}, "SMTP_USERNAME"),
        ({"SMTP_PASSWORD": "password"}, "SMTP_PASSWORD"),
    ],
)
def test_production_password_recovery_rejects_placeholder_values(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        _lifecycle_config(**overrides).validate(production=True)


def test_disabled_password_recovery_does_not_require_provider_values():
    _lifecycle_config(
        PASSWORD_RESET_ENABLED=False,
        PASSWORD_RESET_BASE_URL="https://app.example.com/reset-password",
        SMTP_HOST="smtp.example.com",
        SMTP_FROM_EMAIL="no-reply@example.com",
        SMTP_USERNAME=None,
        SMTP_PASSWORD=None,
    ).validate(production=True)
