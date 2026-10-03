from types import SimpleNamespace

import pytest

from core.lifecycle_config import LifecycleConfig
from integrations.mail.provider import MailProviderError
from integrations.mail.resend import (
    ResendAPIError,
    ResendMailProvider,
    _safe_provider_error_code,
)
from services import mail_transport_service as transport


@pytest.mark.asyncio
async def test_resend_sends_email_with_idempotency_and_rfc_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"id": "resend-message-1"}

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

    monkeypatch.setattr("integrations.mail.resend.httpx.AsyncClient", FakeClient)
    provider = ResendMailProvider(
        SimpleNamespace(
            API_BASE_URL="https://api.resend.com",
            API_TOKEN="re_secret",
            API_TIMEOUT_SECONDS=12,
        )
    )

    receipt = await provider.send(
        sender="news@example.ru",
        sender_name="WB Insight",
        recipient="seller@example.org",
        recipient_name="Иван",
        subject="Отчёт WB Insight",
        body="Текст отчёта",
        html_body="<p>Текст отчёта</p>",
        preview_title="Короткий итог недели",
        reply_to="support@example.ru",
        headers={
            "List-Unsubscribe": "<https://app.example.ru/unsubscribe/token>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "X-WB-Trace": "trace-1",
        },
        idempotency_key="weekly-report:user-1",
    )

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_secret"
    assert captured["headers"]["Idempotency-Key"] == "weekly-report:user-1"
    assert captured["json"]["from"] == "WB Insight <news@example.ru>"
    assert captured["json"]["to"] == ["Иван <seller@example.org>"]
    assert captured["json"]["reply_to"] == "support@example.ru"
    assert "Короткий итог недели" in captured["json"]["html"]
    assert captured["json"]["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert receipt.provider_message_id == "resend-message-1"


@pytest.mark.asyncio
async def test_resend_filters_reserved_headers_and_rejects_injection(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 202

        def json(self):
            return {"id": "resend-message-2"}

    class FakeClient:
        def __init__(self, *, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, _url, *, headers, json):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("integrations.mail.resend.httpx.AsyncClient", FakeClient)
    provider = ResendMailProvider(
        SimpleNamespace(
            API_BASE_URL="https://api.resend.com",
            API_TOKEN="re_secret",
            API_TIMEOUT_SECONDS=10,
        )
    )

    await provider.send(
        sender="no-reply@example.ru",
        recipient="seller@example.org",
        subject="Проверка",
        body="Текст",
        headers={
            "Subject": "Нельзя переопределять",
            "X-WB-Trace": "ok",
        },
    )
    assert captured["json"]["headers"] == {"X-WB-Trace": "ok"}

    with pytest.raises(ValueError, match="Недопустимый почтовый заголовок"):
        await provider.send(
            sender="no-reply@example.ru",
            recipient="seller@example.org",
            subject="Проверка",
            body="Текст",
            headers={"X-WB-Trace": "ok\r\nBcc: attacker@example.org"},
        )


@pytest.mark.asyncio
async def test_resend_classifies_temporary_error(monkeypatch):
    class FakeResponse:
        status_code = 429

        def json(self):
            return {"name": "rate_limit_exceeded", "message": "raw provider text"}

    class FakeClient:
        def __init__(self, *, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("integrations.mail.resend.httpx.AsyncClient", FakeClient)
    provider = ResendMailProvider(
        SimpleNamespace(
            API_BASE_URL="https://api.resend.com",
            API_TOKEN="re_secret",
            API_TIMEOUT_SECONDS=10,
        )
    )

    with pytest.raises(ResendAPIError) as exc_info:
        await provider.send(
            sender="no-reply@example.ru",
            recipient="seller@example.org",
            subject="Проверка",
            body="Текст",
        )

    error = exc_info.value
    assert isinstance(error, MailProviderError)
    assert error.code == "resend_http_429"
    assert error.provider_code == "resend"
    assert error.provider_error_code == "rate_limit_exceeded"
    assert error.retryable is True
    assert "raw provider text" not in str(error)


def test_resend_error_code_extractor_does_not_return_provider_text():
    safe = SimpleNamespace(
        json=lambda: {"name": "validation_error", "message": "секретный контекст"}
    )
    unsafe = SimpleNamespace(
        json=lambda: {"name": "bad code\nAuthorization: Bearer secret"}
    )

    assert _safe_provider_error_code(safe) == "validation_error"
    assert _safe_provider_error_code(unsafe) is None


def test_resend_is_registered_as_marketing_https_provider():
    catalog = {item["code"]: item for item in transport.mail_provider_catalog()}
    resend = catalog["resend"]

    assert set(catalog) == {"smtp", "rusender", "resend"}
    assert resend["capabilities"]["transport_kind"] == "https_api"
    assert resend["capabilities"]["outbound_port"] == 443
    assert resend["capabilities"]["marketing"] is True
    assert resend["capabilities"]["one_click_unsubscribe"] is True
    assert resend["capabilities"]["reply_to"] is True
    assert resend["configuration"]["requires_key_id"] is False
    assert resend["configuration"]["api_base_url"] == "https://api.resend.com"


def test_resend_runtime_is_ready_without_key_id():
    runtime = transport.MailTransportRuntime(
        MAIL_PROVIDER="resend",
        MAIL_DELIVERY_ENABLED=True,
        SMTP_HOST="",
        SMTP_PORT=443,
        SMTP_USERNAME=None,
        SMTP_PASSWORD=None,
        SMTP_FROM_EMAIL="no-reply@example.ru",
        SMTP_FROM_NAME="WB Insight",
        SMTP_REPLY_TO_EMAIL="support@example.ru",
        SMTP_STARTTLS=True,
        SMTP_TIMEOUT_SECONDS=10,
        API_BASE_URL="https://api.resend.com",
        API_TOKEN="re_secret",
        API_TIMEOUT_SECONDS=10,
        source="database",
    )

    assert runtime.ready is True
    assert runtime.credentials_configured is True
    assert isinstance(transport.mail_provider_for_runtime(runtime), ResendMailProvider)


def test_lifecycle_config_accepts_resend_for_marketing_in_environment():
    config = LifecycleConfig()
    config.MAIL_PROVIDER = "resend"
    config.MAIL_CONFIG_SOURCE = "environment"
    config.MAIL_DELIVERY_ENABLED = True
    config.EMAIL_VERIFICATION_ENABLED = False
    config.PASSWORD_RESET_ENABLED = False
    config.SMTP_FROM_EMAIL = "news@wb-insight.ru"
    config.SMTP_FROM_NAME = "WB Insight"
    config.SMTP_REPLY_TO_EMAIL = "support@wb-insight.ru"
    config.RESEND_API_BASE_URL = "https://api.resend.com"
    config.RESEND_API_TOKEN = "re_live_secret"
    config.RESEND_TIMEOUT_SECONDS = 10
    config.MAIL_UNSUBSCRIBE_BASE_URL = "https://wb-insight.ru/api/account/mail/unsubscribe"
    config.MAIL_UNSUBSCRIBE_HMAC_KEY = "x" * 40

    config.validate(production=True)


def test_lifecycle_config_rejects_placeholder_resend_secret_in_production():
    config = LifecycleConfig()
    config.MAIL_PROVIDER = "resend"
    config.MAIL_CONFIG_SOURCE = "environment"
    config.MAIL_DELIVERY_ENABLED = False
    config.EMAIL_VERIFICATION_ENABLED = True
    config.EMAIL_VERIFICATION_BASE_URL = "https://wb-insight.ru/verify-email"
    config.PASSWORD_RESET_ENABLED = False
    config.SMTP_FROM_EMAIL = "no-reply@wb-insight.ru"
    config.RESEND_API_BASE_URL = "https://api.resend.com"
    config.RESEND_API_TOKEN = "replace-with-resend-api-token"
    config.RESEND_TIMEOUT_SECONDS = 10

    with pytest.raises(RuntimeError, match="RESEND_API_TOKEN"):
        config.validate(production=True)
