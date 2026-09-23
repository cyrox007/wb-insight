from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from handlers.dashboard.biling_handler import create_payment_handler, pay_now, router as billing_router
from handlers.dashboard.profile_handler import _public_token
from models.subscription_model import Subscription, SubscriptionStatus
from models.tokens_model import Marketplace
from services import payment_provider_service as provider_service
from settings import config


@pytest.mark.asyncio
async def test_fake_billing_is_disabled_by_default():
    assert config.ALLOW_FAKE_BILLING is False

    request = SimpleNamespace()
    response = Response()
    result = await create_payment_handler(request, response, None)

    assert response.status_code == 503
    assert result["error"]["code"] == "BILLING_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_fake_pay_now_is_disabled_by_default():
    request = SimpleNamespace()
    response = Response()
    result = await pay_now(request, response, None)

    assert response.status_code == 503
    assert result["error"]["code"] == "BILLING_NOT_CONFIGURED"


def test_demo_subscription_is_active_inside_period():
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        status=SubscriptionStatus.DEMO,
        current_period_start=now - timedelta(minutes=1),
        current_period_end=now + timedelta(days=7),
    )

    assert subscription.is_active is True


def test_profile_never_serializes_token_ciphertext():
    token = SimpleNamespace(
        id="token-id",
        label="Main WB",
        marketplace=Marketplace.WILDBERRIES,
        token_type="personal",
        encrypted_token="VERY_SECRET_CIPHERTEXT",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_active=True,
        is_revoked=False,
        is_valid=True,
    )

    payload = _public_token(token)

    assert "VERY_SECRET_CIPHERTEXT" not in payload.values()
    assert "encrypted_token" not in payload



def test_sber_callback_openapi_operations_are_unique():
    callback_routes = [
        route
        for route in billing_router.routes
        if getattr(route, "path", "") == "/billing/sber/callback"
    ]

    assert len(callback_routes) == 2
    operation_ids = {route.operation_id for route in callback_routes}
    assert operation_ids == {"sber_callback_get", "sber_callback_post"}



@pytest.mark.parametrize("value", ["false", "true", "0", "1", 0, 1, None])
def test_payment_admin_flags_accept_only_json_boolean(value):
    with pytest.raises(ValueError, match="логическим значением"):
        provider_service._optional_bool({"enabled": value}, "enabled")


def test_payment_admin_flags_preserve_real_boolean_values():
    assert provider_service._optional_bool({"enabled": False}, "enabled") is False
    assert provider_service._optional_bool({"enabled": True}, "enabled") is True
    assert provider_service._optional_bool({}, "enabled") is None



@pytest.mark.parametrize(
    ("mode", "url"),
    [
        ("test", "https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1"),
        ("test", "https://ecomtest.sberbank.ru/ecomm/gw/partner/api/v1/"),
        ("live", "https://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1"),
    ],
)
def test_sber_managed_gateway_accepts_only_expected_sber_routes(mode, url):
    normalized = provider_service._normalize_sber_gateway_url(url, mode)

    assert normalized.startswith("https://")
    assert normalized.endswith("/ecomm/gw/partner/api/v1")


@pytest.mark.parametrize(
    ("mode", "url"),
    [
        ("live", "https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1"),
        ("test", "https://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1"),
        ("live", "https://attacker.example/ecomm/gw/partner/api/v1"),
        ("live", "http://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1"),
        ("live", "https://user:pass@ecommerce.sberbank.ru/ecomm/gw/partner/api/v1"),
        ("live", "https://ecommerce.sberbank.ru/other/api/v1"),
        ("live", "https://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1?redirect=x"),
    ],
)
def test_sber_managed_gateway_rejects_unsafe_or_wrong_mode_urls(mode, url):
    with pytest.raises(ValueError):
        provider_service._normalize_sber_gateway_url(url, mode)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0, -1, 121])
def test_payment_provider_timeout_rejects_non_finite_and_out_of_range_values(value):
    with pytest.raises(ValueError, match="Таймаут"):
        provider_service._normalize_timeout(value)


def test_sber_runtime_marks_legacy_unsafe_gateway_not_ready(monkeypatch):
    row = SimpleNamespace(
        api_base_url="https://attacker.example/ecomm/gw/partner/api/v1",
        return_url="https://app.example.test/billing/success",
        fail_url="https://app.example.test/billing/fail",
        currency_code="643",
        timeout_seconds=10,
        enabled=True,
        is_default=True,
        options={},
    )
    monkeypatch.setattr(
        provider_service,
        "_read_secrets",
        lambda _row: {"username": "merchant", "password": "secret"},
    )

    runtime = provider_service._effective_runtime(row, "sber", "live")

    assert runtime.ready is False
    assert runtime.api_base_url == row.api_base_url


@pytest.mark.asyncio
async def test_provider_config_validation_failure_occurs_inside_savepoint(monkeypatch):
    row = SimpleNamespace(
        id="provider-id",
        provider="sber",
        mode="live",
        api_base_url="https://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1",
        return_url=None,
        fail_url=None,
        currency_code="643",
        timeout_seconds=10,
        enabled=False,
        is_default=False,
        options={},
        encrypted_secrets=None,
        updated_by=None,
    )

    class NestedTransaction:
        def __init__(self):
            self.exception_type = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, _exc, _tb):
            self.exception_type = exc_type
            return False

    class Session:
        def __init__(self):
            self.nested = NestedTransaction()
            self.flush_count = 0

        def begin_nested(self):
            return self.nested

        async def flush(self):
            self.flush_count += 1

        async def execute(self, _statement):
            raise AssertionError("Обновление default-провайдера не ожидалось")

    session = Session()

    async def existing_config(_session, _provider, _mode):
        return row

    monkeypatch.setattr(provider_service, "get_provider_config", existing_config)
    monkeypatch.setattr(
        provider_service,
        "_read_secrets",
        lambda _row: {"username": "merchant", "password": "secret"},
    )
    monkeypatch.setattr(
        provider_service,
        "encrypt_secret_payload",
        lambda *_args, **_kwargs: "encrypted",
    )

    with pytest.raises(ValueError, match="конфигурация не готова"):
        await provider_service.upsert_provider_config(
            session,
            provider="sber",
            mode="live",
            actor_id=SimpleNamespace(),
            values={"enabled": True},
        )

    assert session.nested.exception_type is ValueError
    assert session.flush_count == 1
