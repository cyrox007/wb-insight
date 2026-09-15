from types import SimpleNamespace

import pytest

from integrations.marketplace import MarketplaceAdapterNotFoundError
from integrations.registry import get_marketplace_adapter
from models.tokens_model import Marketplace
from sync import router


def test_wildberries_adapter_is_registered():
    adapter = get_marketplace_adapter(Marketplace.WILDBERRIES)

    assert adapter.marketplace == Marketplace.WILDBERRIES
    assert "orders" in adapter.handlers
    assert "finance_summary" in adapter.handlers


def test_unimplemented_marketplace_has_explicit_adapter_error():
    with pytest.raises(MarketplaceAdapterNotFoundError) as exc_info:
        get_marketplace_adapter(Marketplace.OZON)

    assert exc_info.value.marketplace == Marketplace.OZON


@pytest.mark.asyncio
async def test_generic_router_dispatches_by_token_marketplace(monkeypatch):
    calls = []

    class FakeAdapter:
        async def sync_entity(self, session, job, token):
            calls.append((session, job, token))

    adapter = FakeAdapter()
    session = object()
    job = SimpleNamespace(entity="stocks")
    token = SimpleNamespace(marketplace=Marketplace.WILDBERRIES)

    def fake_get_marketplace_adapter(marketplace):
        assert marketplace == Marketplace.WILDBERRIES
        return adapter

    monkeypatch.setattr(router, "get_marketplace_adapter", fake_get_marketplace_adapter)

    await router.call_marketplace_api(session=session, job=job, token=token)

    assert calls == [(session, job, token)]


@pytest.mark.asyncio
async def test_legacy_wb_router_uses_generic_dispatch(monkeypatch):
    calls = []

    async def fake_call_marketplace_api(*, session, job, token):
        calls.append((session, job, token))

    session = object()
    job = SimpleNamespace(entity="orders")
    token = SimpleNamespace(marketplace=Marketplace.WILDBERRIES)

    monkeypatch.setattr(router, "call_marketplace_api", fake_call_marketplace_api)

    await router.call_wb_api(session=session, job=job, token=token)

    assert calls == [(session, job, token)]
