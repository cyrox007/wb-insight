from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.mail.rusender import RuSenderAPIError, RuSenderMailProvider
from integrations.mail.smtp import SMTPMailProvider
from services import mail_transport_service as transport
from services import mail_unsubscribe_service as unsubscribe
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



def test_signed_unsubscribe_token_round_trip_and_tamper_rejection(monkeypatch):
    monkeypatch.setattr(
        unsubscribe.lifecycle_config,
        "MAIL_UNSUBSCRIBE_HMAC_KEY",
        "independent-mail-unsubscribe-secret-1234567890",
    )
    monkeypatch.setattr(
        unsubscribe.lifecycle_config,
        "MAIL_UNSUBSCRIBE_BASE_URL",
        "https://app.example.net/api/account/mail/unsubscribe",
    )

    token = unsubscribe.create_unsubscribe_token(
        email="SELLER@example.net",
        user_id="5cad7ec0-2b52-4d41-bccb-c47035fc73d1",
    )
    identity = unsubscribe.parse_unsubscribe_token(token)

    assert identity.email == "seller@example.net"
    assert identity.user_id == "5cad7ec0-2b52-4d41-bccb-c47035fc73d1"
    assert identity.list_id == "marketing"
    assert token in unsubscribe.unsubscribe_url(
        email="seller@example.net",
        user_id=identity.user_id,
    )

    with pytest.raises(ValueError, match="unsubscribe_token_invalid"):
        unsubscribe.parse_unsubscribe_token(token[:-1] + ("A" if token[-1] != "A" else "B"))



def test_smtp_provider_emits_sender_identity_and_bulk_headers(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, **_kwargs):
            return None

        def login(self, *_args, **_kwargs):
            return None

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr("integrations.mail.smtp.smtplib.SMTP", FakeSMTP)

    provider = SMTPMailProvider(
        SimpleNamespace(
            SMTP_HOST="smtp.example.net",
            SMTP_PORT=587,
            SMTP_TIMEOUT_SECONDS=10,
            SMTP_STARTTLS=True,
            SMTP_USERNAME=None,
            SMTP_PASSWORD=None,
        )
    )
    provider._send_sync(
        sender="news@example.net",
        sender_name="WB Insight",
        reply_to="support@example.net",
        recipient="seller@example.org",
        subject="Новости",
        body="Текст",
        html_body="<p>Текст</p>",
        headers={
            "List-Unsubscribe": "<https://app.example.net/unsubscribe/token>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "List-ID": "WB Insight marketing <marketing.example.net>",
            "Precedence": "bulk",
        },
    )

    message = sent["message"]
    assert message["From"] == "WB Insight <news@example.net>"
    assert message["Reply-To"] == "support@example.net"
    assert message["Date"]
    assert message["Message-ID"].endswith("@example.net>")
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["Precedence"] == "bulk"
    assert message.is_multipart()


@pytest.mark.asyncio
async def test_rusender_provider_uses_bearer_key_id_and_idempotency(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"uuid": "018e1234-abcd-7000-8000-000000000001"}

    class FakeClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("integrations.mail.rusender.httpx.AsyncClient", FakeClient)

    provider = RuSenderMailProvider(
        SimpleNamespace(
            RUSENDER_API_BASE_URL="https://api.rusender.ru",
            RUSENDER_KEY_ID="15074",
            RUSENDER_API_TOKEN="secret-token",
            RUSENDER_TIMEOUT_SECONDS=12,
        )
    )
    receipt = await provider.send(
        sender="no-reply@mail.jsinteractive.ru",
        sender_name="WB Insight",
        recipient="seller@example.org",
        subject="Подтверждение email",
        body="Текст",
        html_body="<p>Текст</p>",
        idempotency_key="verify:abc",
        headers={"List-Unsubscribe": "<https://ignored.example>", "X-WB-Trace": "trace-1"},
    )

    assert captured["url"] == "https://api.rusender.ru/api/v1/external-mails/send/15074"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["json"]["idempotencyKey"] == "verify:abc"
    assert captured["json"]["mail"]["from"]["email"] == "no-reply@mail.jsinteractive.ru"
    assert captured["json"]["mail"]["html"] == "<p>Текст</p>"
    assert captured["json"]["mail"]["text"] == "Текст"
    assert captured["json"]["mail"]["headers"] == {"X-WB-Trace": "trace-1"}
    assert receipt.provider_message_id == "018e1234-abcd-7000-8000-000000000001"


@pytest.mark.asyncio
async def test_rusender_provider_classifies_retryable_statuses(monkeypatch):
    class FakeResponse:
        status_code = 429

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, *, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("integrations.mail.rusender.httpx.AsyncClient", FakeClient)
    provider = RuSenderMailProvider(
        SimpleNamespace(
            RUSENDER_API_BASE_URL="https://api.rusender.ru",
            RUSENDER_KEY_ID="15074",
            RUSENDER_API_TOKEN="secret-token",
            RUSENDER_TIMEOUT_SECONDS=10,
        )
    )

    with pytest.raises(RuSenderAPIError) as exc_info:
        await provider.send(
            sender="no-reply@mail.jsinteractive.ru",
            recipient="seller@example.org",
            subject="Test",
            body="Text",
        )

    assert exc_info.value.code == "rusender_http_429"
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_rusender_transport_encrypts_token_and_hides_it_from_payload(monkeypatch):
    session = _FakeSession()
    captured = {}

    async def no_existing(_session):
        return None

    def fake_encrypt(payload, *, context):
        captured["payload"] = dict(payload)
        captured["context"] = context
        return "encrypted-rusender"

    monkeypatch.setattr(transport, "get_mail_provider_config", no_existing)
    monkeypatch.setattr(transport, "encrypt_secret_payload", fake_encrypt)
    monkeypatch.setattr(transport.lifecycle_config, "MAIL_CONFIG_SOURCE", "auto")
    monkeypatch.setattr(transport.config, "IS_PRODUCTION", False)

    row = await transport.upsert_mail_transport(
        session,
        actor_id=uuid4(),
        values={
            "provider": "rusender",
            "from_email": "no-reply@mail.jsinteractive.ru",
            "from_name": "WB Insight",
            "key_id": "15074",
            "api_token": "rs_ck_v1_secret",
            "timeout_seconds": 10,
        },
    )

    assert row.provider == "rusender"
    assert row.host == "https://api.rusender.ru"
    assert row.enabled is False
    assert captured["payload"] == {
        "key_id": "15074",
        "api_token": "rs_ck_v1_secret",
    }
    assert captured["context"] == "mail-provider:rusender"


def test_smtp_provider_rejects_header_injection(monkeypatch):
    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("integrations.mail.smtp.smtplib.SMTP", FakeSMTP)

    provider = SMTPMailProvider(
        SimpleNamespace(
            SMTP_HOST="smtp.example.net",
            SMTP_PORT=587,
            SMTP_TIMEOUT_SECONDS=10,
            SMTP_STARTTLS=False,
            SMTP_USERNAME=None,
            SMTP_PASSWORD=None,
        )
    )
    with pytest.raises(ValueError, match="unsafe_mail_header"):
        provider._send_sync(
            sender="news@example.net",
            recipient="seller@example.org",
            subject="Новости",
            body="Текст",
            headers={"X-Test": "ok\r\nBcc: attacker@example.org"},
        )
