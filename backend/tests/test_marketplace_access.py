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
