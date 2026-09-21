import pytest

from core.lifecycle_config import lifecycle_config
from services import mail_service


def test_password_reset_secret_is_kept_in_url_fragment(monkeypatch):
    monkeypatch.setattr(
        lifecycle_config,
        "PASSWORD_RESET_BASE_URL",
        "https://app.example.com/reset-password",
    )

    url = mail_service._password_reset_url("secret-token")

    assert url == "https://app.example.com/reset-password#token=secret-token"
    assert "?token=" not in url


def test_production_password_recovery_requires_starttls(monkeypatch):
    monkeypatch.setattr(lifecycle_config, "PASSWORD_RESET_ENABLED", True)
    monkeypatch.setattr(
        lifecycle_config,
        "PASSWORD_RESET_BASE_URL",
        "https://app.example.com/reset-password",
    )
    monkeypatch.setattr(lifecycle_config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(lifecycle_config, "SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setattr(lifecycle_config, "SMTP_STARTTLS", False)
    monkeypatch.setattr(lifecycle_config, "SMTP_USERNAME", None)
    monkeypatch.setattr(lifecycle_config, "SMTP_PASSWORD", None)

    with pytest.raises(RuntimeError, match="SMTP_STARTTLS"):
        lifecycle_config.validate(production=True)



def test_auto_mail_source_allows_database_bootstrap_with_placeholder_env(monkeypatch):
    monkeypatch.setattr(lifecycle_config, "PASSWORD_RESET_ENABLED", True)
    monkeypatch.setattr(
        lifecycle_config,
        "PASSWORD_RESET_BASE_URL",
        "https://app.jsinteractive.ru/reset-password",
    )
    monkeypatch.setattr(lifecycle_config, "EMAIL_VERIFICATION_ENABLED", False)
    monkeypatch.setattr(lifecycle_config, "MAIL_DELIVERY_ENABLED", False)
    monkeypatch.setattr(lifecycle_config, "MAIL_CONFIG_SOURCE", "auto")
    monkeypatch.setattr(lifecycle_config, "MAIL_PROVIDER", "smtp")
    monkeypatch.setattr(lifecycle_config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(lifecycle_config, "SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setattr(lifecycle_config, "SMTP_STARTTLS", False)
    monkeypatch.setattr(lifecycle_config, "SMTP_USERNAME", None)
    monkeypatch.setattr(lifecycle_config, "SMTP_PASSWORD", None)

    # Import/startup cannot know whether encrypted DB mail config exists. In
    # auto mode it validates the feature URL now and defers provider fallback
    # validation until runtime selection has checked the DB.
    lifecycle_config.validate(production=True)
