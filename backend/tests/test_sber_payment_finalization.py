from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.sber.client import SberOrderStatus
from models.payments_model import PaymentProvider, PaymentStatus
from services import payment_service


class FakeSession:
    async def flush(self):
        return None


def make_payment():
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        tariff_id=uuid4(),
        provider=PaymentProvider.SBER,
        status=PaymentStatus.PENDING,
        provider_status=None,
        provider_data=None,
        confirmed_at=None,
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_deposited_payment_activates_subscription_once(monkeypatch):
    payment = make_payment()
    created_subscription = SimpleNamespace(id=uuid4())
    calls = {"deactivate": 0, "create": 0, "event": 0}
    subscription_by_payment = {"value": None}

    async def get_locked(_session, payment_id):
        assert payment_id == payment.id
        return payment

    async def get_subscription(_session, payment_id):
        assert payment_id == payment.id
        return subscription_by_payment["value"]

    async def user_active(_session, user_id):
        assert user_id == payment.user_id
        return True

    async def deactivate(_session, user_id):
        assert user_id == payment.user_id
        calls["deactivate"] += 1

    async def create(_session, user_id, tariff_id, *, payment_id=None):
        assert user_id == payment.user_id
        assert tariff_id == payment.tariff_id
        assert payment_id == payment.id
        calls["create"] += 1
        subscription_by_payment["value"] = created_subscription
        return created_subscription

    async def record(_session, **kwargs):
        calls["event"] += 1
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(payment_service, "get_payment_for_update", get_locked)
    monkeypatch.setattr(payment_service, "get_subscription_by_payment_id", get_subscription)
    monkeypatch.setattr(payment_service, "is_payment_user_active", user_active)
    monkeypatch.setattr(payment_service, "deactivate_active_subscriptions", deactivate)
    monkeypatch.setattr(payment_service, "create_subscription", create)
    monkeypatch.setattr(payment_service, "record_payment_event", record)

    bank_status = SberOrderStatus(
        order_status=2,
        payment_state="DEPOSITED",
        raw={"orderStatus": 2, "paymentState": "DEPOSITED"},
    )

    first_payment, first_subscription = await payment_service.apply_sber_status(
        FakeSession(),  # type: ignore[arg-type]
        payment_id=payment.id,
        status=bank_status,
    )
    second_payment, second_subscription = await payment_service.apply_sber_status(
        FakeSession(),  # type: ignore[arg-type]
        payment_id=payment.id,
        status=bank_status,
        event_type="callback_verified",
    )

    assert first_payment.status == PaymentStatus.SUCCEEDED
    assert first_payment.confirmed_at is not None
    assert first_subscription is created_subscription
    assert second_payment.status == PaymentStatus.SUCCEEDED
    assert second_subscription is created_subscription
    assert calls["deactivate"] == 1
    assert calls["create"] == 1
    assert calls["event"] == 2


@pytest.mark.asyncio
async def test_deposited_payment_does_not_reactivate_inactive_account(monkeypatch):
    payment = make_payment()
    calls = {"deactivate": 0, "create": 0, "events": []}

    async def get_locked(_session, _payment_id):
        return payment

    async def no_subscription(_session, _payment_id):
        return None

    async def user_inactive(_session, user_id):
        assert user_id == payment.user_id
        return False

    async def deactivate(*_args, **_kwargs):
        calls["deactivate"] += 1

    async def create(*_args, **_kwargs):
        calls["create"] += 1

    async def record(_session, **kwargs):
        calls["events"].append(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(payment_service, "get_payment_for_update", get_locked)
    monkeypatch.setattr(payment_service, "get_subscription_by_payment_id", no_subscription)
    monkeypatch.setattr(payment_service, "is_payment_user_active", user_inactive)
    monkeypatch.setattr(payment_service, "deactivate_active_subscriptions", deactivate)
    monkeypatch.setattr(payment_service, "create_subscription", create)
    monkeypatch.setattr(payment_service, "record_payment_event", record)

    bank_status = SberOrderStatus(
        order_status=2,
        payment_state="DEPOSITED",
        raw={"orderStatus": 2, "paymentState": "DEPOSITED"},
    )
    result, subscription = await payment_service.apply_sber_status(
        FakeSession(),  # type: ignore[arg-type]
        payment_id=payment.id,
        status=bank_status,
        event_type="callback_verified",
    )

    assert result.status == PaymentStatus.SUCCEEDED
    assert result.confirmed_at is not None
    assert subscription is None
    assert calls["deactivate"] == 0
    assert calls["create"] == 0
    assert [event["event_type"] for event in calls["events"]] == [
        "callback_verified",
        "subscription_activation_skipped",
    ]
    assert calls["events"][-1]["provider_data"] == {"reason": "inactive_account"}


@pytest.mark.asyncio
async def test_pending_bank_state_never_activates_subscription(monkeypatch):
    payment = make_payment()
    calls = {"create": 0}

    async def get_locked(_session, _payment_id):
        return payment

    async def no_subscription(_session, _payment_id):
        return None

    async def create(*_args, **_kwargs):
        calls["create"] += 1

    async def record(_session, **kwargs):
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(payment_service, "get_payment_for_update", get_locked)
    monkeypatch.setattr(payment_service, "get_subscription_by_payment_id", no_subscription)
    monkeypatch.setattr(payment_service, "create_subscription", create)
    monkeypatch.setattr(payment_service, "record_payment_event", record)

    bank_status = SberOrderStatus(
        order_status=0,
        payment_state="CREATED",
        raw={"orderStatus": 0, "paymentState": "CREATED"},
    )
    result, subscription = await payment_service.apply_sber_status(
        FakeSession(),  # type: ignore[arg-type]
        payment_id=payment.id,
        status=bank_status,
    )

    assert result.status == PaymentStatus.PENDING
    assert subscription is None
    assert calls["create"] == 0
