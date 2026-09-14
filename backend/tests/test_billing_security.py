from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from handlers.dashboard.biling_handler import create_payment_handler, pay_now
from handlers.dashboard.profile_handler import _public_token
from models.subscription_model import Subscription, SubscriptionStatus
from models.tokens_model import Marketplace
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
    assert payload["encrypted_token"] == "••••••••"
