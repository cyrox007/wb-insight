from types import SimpleNamespace
from uuid import uuid4

import pytest

from services import mail_transport_service as transport
from utils.mail_html import html_to_text, render_mail_document, sanitize_mail_html


def test_mail_html_sanitizer_blocks_active_content_and_unsafe_images():
    raw = """
    <h2 onclick="alert(1)" style="color:red">Привет<script>alert(1)</script></h2>
    <p>Текст <strong>жирный</strong></p>
    <img src="http://unsafe.example/image.jpg" onerror="alert(1)">
    <img src="https://cdn.example.com/banner.jpg" alt="Баннер" onerror="alert(1)">
    <a href="javascript:alert(1)" data-mail-button="1">bad</a>
    <a href="https://wb.jsinteractive.ru" data-mail-button="1">Открыть</a>
    """
    safe = sanitize_mail_html(raw)

    assert "<script" not in safe
    assert "onclick" not in safe
    assert "onerror" not in safe
    assert "javascript:" not in safe
    assert "http://unsafe.example" not in safe
    assert "https://cdn.example.com/banner.jpg" in safe
    assert "https://wb.jsinteractive.ru" in safe
    assert "background:#6557ff" in safe


def test_mail_html_has_plain_text_fallback_and_document_shell():
    fragment = "<h2>Заголовок</h2><p>Первый <strong>абзац</strong>.</p><p>Второй.</p>"

    text = html_to_text(fragment)
    document = render_mail_document(fragment)

    assert "Заголовок" in text
    assert "Первый абзац." in text
    assert "Второй." in text
    assert "<!doctype html>" in document
    assert fragment != document


@pytest.mark.asyncio
async def test_mail_transport_payload_never_returns_password(monkeypatch):
    runtime = transport.MailTransportRuntime(
        MAIL_PROVIDER="smtp",
        MAIL_DELIVERY_ENABLED=True,
        SMTP_HOST="smtp.example.net",
        SMTP_PORT=587,
        SMTP_USERNAME="mailer-user",
        SMTP_PASSWORD="super-secret",
        SMTP_FROM_EMAIL="no-reply@example.net",
        SMTP_FROM_NAME="WB Insight",
        SMTP_REPLY_TO_EMAIL="support@example.net",
        SMTP_STARTTLS=True,
        SMTP_TIMEOUT_SECONDS=10,
        source="database",
        updated_at=None,
    )

    async def fake_runtime(_session):
        return runtime

    monkeypatch.setattr(transport, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(transport.lifecycle_config, "MAIL_CONFIG_SOURCE", "auto")
    monkeypatch.setattr(
        transport.lifecycle_config,
        "MAIL_UNSUBSCRIBE_BASE_URL",
        "https://app.example.net/api/account/mail/unsubscribe",
    )
    monkeypatch.setattr(
        transport.lifecycle_config,
        "MAIL_UNSUBSCRIBE_HMAC_KEY",
        "x" * 40,
    )

    payload = await transport.mail_transport_payload(object())

    assert payload["credentials_configured"] is True
    assert payload["username_hint"] != "mailer-user"
    assert "password" not in payload
    assert "super-secret" not in str(payload)
    assert payload["from_name"] == "WB Insight"
    assert payload["reply_to_email"] == "support@example.net"
    assert payload["marketing_ready"] is True
    assert payload["deliverability"]["one_click_unsubscribe"] is True


class _FakeSession:
    def __init__(self):
        self.added = []
        self.flushes = 0

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.flushes += 1


@pytest.mark.asyncio
async def test_mail_transport_encrypts_credentials_before_storage(monkeypatch):
    session = _FakeSession()
    captured = {}

    async def no_existing(_session):
        return None

    def fake_encrypt(payload, *, context):
        captured["payload"] = dict(payload)
        captured["context"] = context
        return "encrypted-payload"

    monkeypatch.setattr(transport, "get_mail_provider_config", no_existing)
    monkeypatch.setattr(transport, "encrypt_secret_payload", fake_encrypt)
    monkeypatch.setattr(transport.lifecycle_config, "MAIL_CONFIG_SOURCE", "auto")
    monkeypatch.setattr(transport.config, "IS_PRODUCTION", False)

    row = await transport.upsert_mail_transport(
        session,
        actor_id=uuid4(),
        values={
            "enabled": True,
            "host": "smtp.mail.test",
            "port": 587,
            "from_email": "no-reply@mail.test",
            "starttls": True,
            "timeout_seconds": 10,
            "username": "smtp-user",
            "password": "smtp-password",
        },
    )

    assert row.encrypted_secrets == "encrypted-payload"
    assert captured["payload"] == {
        "username": "smtp-user",
        "password": "smtp-password",
    }
    assert captured["context"] == "mail-provider:smtp"


@pytest.mark.asyncio
async def test_production_mail_transport_requires_starttls(monkeypatch):
    session = _FakeSession()

    async def no_existing(_session):
        return None

    monkeypatch.setattr(transport, "get_mail_provider_config", no_existing)
    monkeypatch.setattr(transport, "encrypt_secret_payload", lambda *_args, **_kwargs: "encrypted")
    monkeypatch.setattr(transport.lifecycle_config, "MAIL_CONFIG_SOURCE", "database")
    monkeypatch.setattr(transport.config, "IS_PRODUCTION", True)

    with pytest.raises(ValueError, match="STARTTLS"):
        await transport.upsert_mail_transport(
            session,
            actor_id=uuid4(),
            values={
                "enabled": True,
                "host": "smtp.mail.test",
                "port": 587,
                "from_email": "no-reply@mail.test",
                "starttls": False,
                "timeout_seconds": 10,
                "username": "smtp-user",
                "password": "smtp-password",
            },
        )



def test_marketing_document_contains_visible_unsubscribe_link():
    url = "https://app.example.net/api/account/mail/unsubscribe/signed-token"
    document = render_mail_document(
        "<h2>Новости</h2><p>Текст письма.</p>",
        unsubscribe_url=url,
    )

    assert url in document
    assert "Отписаться от маркетинговых писем" in document
