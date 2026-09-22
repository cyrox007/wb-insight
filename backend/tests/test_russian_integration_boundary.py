from types import SimpleNamespace

import pytest

from integrations.mail.provider import MailProviderRegistry
from integrations.mail.smtp import SMTPMailProvider
from integrations.marketplace import MarketplaceAdapterNotFoundError
from integrations.sber.client import SberAcquiringClient
from models.tokens_model import Marketplace


def test_marketplace_adapter_error_is_russian():
    error = MarketplaceAdapterNotFoundError(Marketplace.OZON)

    assert str(error) == "Адаптер маркетплейса не настроен: ozon"


def test_mail_provider_registry_errors_are_russian():
    registry = MailProviderRegistry()

    with pytest.raises(ValueError, match="Код почтового провайдера обязателен"):
        registry.register(SimpleNamespace(code=""))

    with pytest.raises(
        RuntimeError,
        match="Почтовый провайдер не зарегистрирован: missing",
    ):
        registry.get("missing")


def test_smtp_rejects_unsafe_header_with_russian_error():
    provider = SMTPMailProvider(
        SimpleNamespace(
            SMTP_HOST="localhost",
            SMTP_PORT=25,
            SMTP_TIMEOUT_SECONDS=1,
            SMTP_STARTTLS=False,
            SMTP_USERNAME="",
            SMTP_PASSWORD="",
        )
    )

    with pytest.raises(ValueError, match="Недопустимый почтовый заголовок"):
        provider._send_sync(
            sender="sender@example.test",
            recipient="recipient@example.test",
            subject="Тест",
            body="Текст",
            headers={"X-Test": "опасное\nзначение"},
        )


@pytest.mark.asyncio
async def test_sber_rejects_non_positive_amount_with_russian_error():
    client = SberAcquiringClient(
        base_url="https://example.test",
        username="test",
        password="test",
        http_client=SimpleNamespace(),
    )

    with pytest.raises(
        ValueError,
        match="Сумма платежа в копейках должна быть больше нуля",
    ):
        await client.register_order(
            order_number="test-order",
            amount_kopecks=0,
            return_url="https://example.test/ok",
            fail_url="https://example.test/fail",
            description="Тест",
        )
