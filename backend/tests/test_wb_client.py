from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.wildberries import client as wb_client_module
from integrations.wildberries.client import WBAuthError, WBClient


class FakeRateLimiter:
    def __init__(self):
        self.acquired = []
        self.cooldowns = []
        self.closed = False

    async def acquire(self, credential_id, endpoint, min_interval_seconds):
        self.acquired.append((credential_id, endpoint, min_interval_seconds))

    async def cooldown(self, credential_id, endpoint, seconds):
        self.cooldowns.append((credential_id, endpoint, seconds))

    async def aclose(self):
        self.closed = True


def make_token():
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        encrypted_token="encrypted-placeholder",
    )


@pytest.fixture(autouse=True)
def transport_settings(monkeypatch):
    monkeypatch.setattr(wb_client_module.config, "WB_API_MIN_INTERVAL_SECONDS", 0.25)
    monkeypatch.setattr(wb_client_module.config, "WB_API_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(wb_client_module.config, "WB_API_BACKOFF_BASE_SECONDS", 0.01)
    monkeypatch.setattr(wb_client_module.config, "WB_API_MAX_BACKOFF_SECONDS", 5.0)
    monkeypatch.setattr(wb_client_module, "decrypt_token", lambda *_args: "raw-secret")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(wb_client_module.asyncio, "sleep", no_sleep)


@pytest.mark.asyncio
async def test_429_retry_after_sets_shared_cooldown_and_retries():
    calls = 0

    async def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.headers["Authorization"] == "raw-secret"
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"data": {"items": []}})

    token = make_token()
    limiter = FakeRateLimiter()
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with WBClient(
        token,
        http_client=http_client,
        rate_limiter=limiter,
    ) as client:
        result = await client.get_stock({"limit": 1, "offset": 0})

    assert result == {"data": {"items": []}}
    assert calls == 2
    assert limiter.cooldowns == [
        (str(token.id), "analytics.stocks_warehouses", 2.0)
    ]
    assert [item[1] for item in limiter.acquired] == [
        "analytics.stocks_warehouses",
        "analytics.stocks_warehouses",
    ]
    assert http_client.is_closed is True
    assert limiter.closed is True


@pytest.mark.asyncio
async def test_auth_error_is_typed_and_not_retried():
    calls = 0

    async def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="do-not-copy-response-body")

    limiter = FakeRateLimiter()
    client = WBClient(
        make_token(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    )

    with pytest.raises(WBAuthError) as exc_info:
        await client.get_products({"settings": {}})

    await client.aclose()

    assert calls == 1
    assert exc_info.value.status_code == 401
    assert exc_info.value.endpoint == "content.cards_list"
    assert "do-not-copy-response-body" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_transient_server_error_retries_within_budget():
    calls = 0

    async def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"cards": []})

    limiter = FakeRateLimiter()
    async with WBClient(
        make_token(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    ) as client:
        result = await client.get_products({"settings": {}})

    assert result == {"cards": []}
    assert calls == 3


@pytest.mark.asyncio
async def test_transport_error_retries_then_succeeds():
    calls = 0

    async def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("temporary connect failure", request=request)
        return httpx.Response(200, json={"adverts": []})

    limiter = FakeRateLimiter()
    async with WBClient(
        make_token(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    ) as client:
        result = await client.get_advert_campaigns({"statuses": "9"})

    assert result == {"adverts": []}
    assert calls == 2
