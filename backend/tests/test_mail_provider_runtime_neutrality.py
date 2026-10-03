from integrations.mail.provider import MailDeliveryReceipt, MailProviderCapabilities
from services import mail_transport_service as transport


class ExampleHTTPSProvider:
    code = "example_api"
    display_name = "Пример HTTPS API"
    configuration_kind = "https_api_key"
    default_port = 443
    default_api_base_url = "https://mail-api.example.test"
    requires_key_id = False
    key_id_numeric = False
    environment_api_base_url_attr = "EXAMPLE_MAIL_API_BASE_URL"
    environment_key_id_attr = None
    environment_api_token_attr = "EXAMPLE_MAIL_API_TOKEN"
    environment_timeout_attr = "EXAMPLE_MAIL_API_TIMEOUT_SECONDS"
    capabilities = MailProviderCapabilities(
        transport_kind="https_api",
        transactional=True,
        marketing=False,
        custom_headers=True,
        preview_title=True,
        idempotency_key=True,
        provider_managed_tls=True,
        provider_managed_ptr=True,
        outbound_port=443,
    )

    def __init__(self, config) -> None:
        self.config = config

    async def send(self, **_kwargs) -> MailDeliveryReceipt:
        return MailDeliveryReceipt(provider_message_id="example-message")


def _register_example_provider(monkeypatch):
    factories = dict(transport._PROVIDER_FACTORIES)
    factories[ExampleHTTPSProvider.code] = ExampleHTTPSProvider
    monkeypatch.setattr(transport, "_PROVIDER_FACTORIES", factories)
    monkeypatch.setattr(transport, "_SUPPORTED_PROVIDERS", frozenset(factories))


def test_https_runtime_uses_generic_api_fields(monkeypatch):
    _register_example_provider(monkeypatch)

    runtime = transport.MailTransportRuntime(
        MAIL_PROVIDER=ExampleHTTPSProvider.code,
        MAIL_DELIVERY_ENABLED=False,
        SMTP_HOST="",
        SMTP_PORT=443,
        SMTP_USERNAME=None,
        SMTP_PASSWORD=None,
        SMTP_FROM_EMAIL="no-reply@example.test",
        SMTP_FROM_NAME="WB Insight",
        SMTP_REPLY_TO_EMAIL=None,
        SMTP_STARTTLS=True,
        SMTP_TIMEOUT_SECONDS=10,
        API_BASE_URL="https://mail-api.example.test",
        API_TOKEN="example-secret",
        API_TIMEOUT_SECONDS=8,
        source="database",
    )

    assert runtime.ready is True
    assert runtime.credentials_configured is True
    assert runtime.API_BASE_URL == "https://mail-api.example.test"
    assert runtime.API_TOKEN == "example-secret"
    assert "RUSENDER_API_TOKEN" not in runtime.__dict__

    provider = transport.mail_provider_for_runtime(runtime)
    assert isinstance(provider, ExampleHTTPSProvider)
    assert provider.config is runtime


def test_environment_runtime_reads_adapter_declared_variables(monkeypatch):
    _register_example_provider(monkeypatch)

    monkeypatch.setattr(
        transport.lifecycle_config,
        "MAIL_PROVIDER",
        ExampleHTTPSProvider.code,
    )
    monkeypatch.setattr(transport.lifecycle_config, "MAIL_DELIVERY_ENABLED", False)
    monkeypatch.setattr(
        transport.lifecycle_config,
        "SMTP_FROM_EMAIL",
        "no-reply@example.test",
    )
    monkeypatch.setattr(transport.lifecycle_config, "SMTP_FROM_NAME", "WB Insight")
    monkeypatch.setattr(
        transport.lifecycle_config,
        "EXAMPLE_MAIL_API_BASE_URL",
        "https://alternate-mail-api.example.test",
        raising=False,
    )
    monkeypatch.setattr(
        transport.lifecycle_config,
        "EXAMPLE_MAIL_API_TOKEN",
        "example-env-secret",
        raising=False,
    )
    monkeypatch.setattr(
        transport.lifecycle_config,
        "EXAMPLE_MAIL_API_TIMEOUT_SECONDS",
        17,
        raising=False,
    )

    runtime = transport._environment_runtime()

    assert runtime.MAIL_PROVIDER == ExampleHTTPSProvider.code
    assert runtime.API_BASE_URL == "https://alternate-mail-api.example.test"
    assert runtime.API_TOKEN == "example-env-secret"
    assert runtime.API_TIMEOUT_SECONDS == 17
    assert runtime.API_KEY_ID is None
    assert runtime.ready is True


def test_legacy_rusender_runtime_names_are_only_compatibility_aliases():
    runtime = transport.MailTransportRuntime(
        MAIL_PROVIDER="rusender",
        MAIL_DELIVERY_ENABLED=False,
        SMTP_HOST="",
        SMTP_PORT=443,
        SMTP_USERNAME=None,
        SMTP_PASSWORD=None,
        SMTP_FROM_EMAIL="no-reply@example.test",
        SMTP_FROM_NAME="WB Insight",
        SMTP_REPLY_TO_EMAIL=None,
        SMTP_STARTTLS=True,
        SMTP_TIMEOUT_SECONDS=10,
        RUSENDER_API_BASE_URL="https://api.rusender.ru",
        RUSENDER_KEY_ID="15074",
        RUSENDER_API_TOKEN="legacy-secret",
        RUSENDER_TIMEOUT_SECONDS=12,
        source="database",
    )

    assert runtime.API_BASE_URL == "https://api.rusender.ru"
    assert runtime.API_KEY_ID == "15074"
    assert runtime.API_TOKEN == "legacy-secret"
    assert runtime.API_TIMEOUT_SECONDS == 12
    assert runtime.RUSENDER_API_TOKEN == "legacy-secret"
    assert "RUSENDER_API_TOKEN" not in runtime.__dict__
