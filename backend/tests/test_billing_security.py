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
