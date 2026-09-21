from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from models.tokens_model import Marketplace
from services import marketplace_access_service


@pytest.mark.asyncio
async def test_allowed_wb_tokens_are_deterministically_limited(monkeypatch):
    now = datetime.now(timezone.utc)
    tokens = [
        SimpleNamespace(
            id="later",
            marketplace=Marketplace.WILDBERRIES,
            is_valid=True,
            issued_at=now,
        ),
        SimpleNamespace(
            id="earlier",
            marketplace=Marketplace.WILDBERRIES,
            is_valid=True,
            issued_at=now - timedelta(days=1),
        ),
        SimpleNamespace(
            id="ozon",
            marketplace=Marketplace.OZON,
            is_valid=True,
            issued_at=now - timedelta(days=2),
        ),
    ]

    async def fake_limit(_session, _user_id):
        return 1

    async def fake_tokens(_session, _user_id):
        return tokens

    monkeypatch.setattr(marketplace_access_service, "get_wb_account_limit", fake_limit)
    monkeypatch.setattr(marketplace_access_service, "get_tokens_by_user_id", fake_tokens)

    result = await marketplace_access_service.get_allowed_wb_tokens(object(), "user-id")

    assert [token.id for token in result] == ["earlier"]


@pytest.mark.asyncio
async def test_no_subscription_means_no_worker_tokens(monkeypatch):
    async def fake_limit(_session, _user_id):
        return 0

    monkeypatch.setattr(marketplace_access_service, "get_wb_account_limit", fake_limit)

    result = await marketplace_access_service.get_allowed_wb_tokens(object(), "user-id")

    assert result == []


class FakeQuotaToken:
    def __init__(self, token_id="wb-1"):
        self.id = token_id
        self.marketplace = Marketplace.WILDBERRIES
        self.issued_at = datetime.now(timezone.utc)
        self.is_active = True
        self.is_revoked = False

    @property
    def is_valid(self):
        return self.is_active and not self.is_revoked


class FakeQuotaSession:
    def __init__(self):
        self.flushed = 0

    async def flush(self):
        self.flushed += 1


@pytest.mark.asyncio
async def test_full_quota_releases_confirmed_revoked_token(monkeypatch):
    token = FakeQuotaToken()
    session = FakeQuotaSession()

    async def fake_limit(_session, _user_id):
        return 1

    async def fake_tokens(_session, _user_id):
        return [token]

    async def fake_probe(_token, _user_id):
        return "rejected"

    monkeypatch.setattr(marketplace_access_service, "get_wb_account_limit", fake_limit)
    monkeypatch.setattr(marketplace_access_service, "get_tokens_by_user_id", fake_tokens)
    monkeypatch.setattr(marketplace_access_service, "_probe_stored_wb_token", fake_probe)

    result = await marketplace_access_service.get_wb_account_quota(session, "user-id")

    assert result == {"allowed": True, "code": None, "limit": 1, "used": 0}
    assert token.is_active is False
    assert token.is_revoked is True
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_full_quota_keeps_slot_when_live_check_is_inconclusive(monkeypatch):
    token = FakeQuotaToken()
    session = FakeQuotaSession()

    async def fake_limit(_session, _user_id):
        return 1

    async def fake_tokens(_session, _user_id):
        return [token]

    async def fake_probe(_token, _user_id):
        return "unknown"

    monkeypatch.setattr(marketplace_access_service, "get_wb_account_limit", fake_limit)
    monkeypatch.setattr(marketplace_access_service, "get_tokens_by_user_id", fake_tokens)
    monkeypatch.setattr(marketplace_access_service, "_probe_stored_wb_token", fake_probe)

    result = await marketplace_access_service.get_wb_account_quota(session, "user-id")

    assert result == {
        "allowed": False,
        "code": "TOKEN_LIMIT_EXCEEDED",
        "limit": 1,
        "used": 1,
    }
    assert token.is_active is True
    assert token.is_revoked is False
    assert session.flushed == 0


@pytest.mark.asyncio
async def test_wb_account_limit_is_driven_by_subscription_tariff_limit(monkeypatch):
    tariff_id = "demo-tariff-id"

    async def fake_subscription(_session, _user_id):
        return SimpleNamespace(tariff_id=tariff_id)

    async def fake_limit(*, session, tariff_id: str, limit_type: str):
        assert tariff_id == "demo-tariff-id"
        assert limit_type == "wb_accounts"
        return SimpleNamespace(limit_value=2)

    monkeypatch.setattr(
        marketplace_access_service,
        "get_active_subscription",
        fake_subscription,
    )
    monkeypatch.setattr(marketplace_access_service, "get_limit", fake_limit)

    result = await marketplace_access_service.get_wb_account_limit(
        object(),
        "user-id",
    )

    assert result == 2


@pytest.mark.asyncio
async def test_missing_wb_account_limit_fails_closed(monkeypatch):
    async def fake_subscription(_session, _user_id):
        return SimpleNamespace(tariff_id="tariff-id")

    async def fake_limit(**_kwargs):
        return None

    monkeypatch.setattr(
        marketplace_access_service,
        "get_active_subscription",
        fake_subscription,
    )
    monkeypatch.setattr(marketplace_access_service, "get_limit", fake_limit)

    result = await marketplace_access_service.get_wb_account_limit(
        object(),
        "user-id",
    )

    assert result == 0
