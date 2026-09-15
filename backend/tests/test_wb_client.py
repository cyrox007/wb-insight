from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.wildberries import client as wb_client_module
from integrations.wildberries.client import WBAuthError, WBClient, WBPermissionError


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


def make_token(token_type="base"):
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        encrypted_token="encrypted-placeholder",
        token_type=token_type,
    )


@pytest.fixture(autouse=True)
def transport_settings(monkeypatch):
    monkeypatch.setattr(wb_client_module.config, "WB_API_MIN_INTERVAL_SECONDS", 0.25)
    monkeypatch.setattr(wb_client_module.config, "WB_API_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(wb_client_module.config, "WB_API_BACKOFF_BASE_SECONDS", 0.01)
    monkeypatch.setattr(wb_client_module.config, "WB_API_MAX_BACKOFF_SECONDS", 5.0)
    monkeypatch.setattr(wb_client_module.config, "WB_SERVICE_SECRET", "test-service-secret")
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
        assert request.headers["Authorization"] == "Bearer raw-secret"
        assert request.headers["X-Client-Secret"] == "test-service-secret"
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
@pytest.mark.parametrize("token_type", ["base", "service"])
async def test_partner_tokens_include_x_client_secret(token_type):
    async def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer raw-secret"
        assert request.headers["X-Client-Secret"] == "test-service-secret"
        return httpx.Response(200, json={"cards": []})

    limiter = FakeRateLimiter()
    async with WBClient(
        make_token(token_type),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    ) as client:
        result = await client.get_products({"settings": {}})

    assert result == {"cards": []}


@pytest.mark.asyncio
async def test_partner_token_fails_closed_without_service_secret(monkeypatch):
    monkeypatch.setattr(wb_client_module.config, "WB_SERVICE_SECRET", None)
    limiter = FakeRateLimiter()
    client = WBClient(
        make_token("base"),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200))
        ),
        rate_limiter=limiter,
    )

    with pytest.raises(WBAuthError, match="service secret"):
        await client.get_products({"settings": {}})

    await client.aclose()


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
async def test_permission_error_is_typed_and_does_not_look_like_auth_failure():
    calls = 0

    async def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(403, text="promotion category is missing")

    limiter = FakeRateLimiter()
    client = WBClient(
        make_token(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    )

    with pytest.raises(WBPermissionError) as exc_info:
        await client.get_advert_stats(
            {"ids": "123", "beginDate": "2026-09-01", "endDate": "2026-09-14"}
        )

    await client.aclose()

    assert calls == 1
    assert exc_info.value.status_code == 403
    assert exc_info.value.endpoint == "promotion.fullstats"
    assert "promotion category is missing" not in str(exc_info.value)


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


@pytest.mark.asyncio
async def test_limiter_closes_even_if_http_client_close_fails():
    class FailingCloseClient:
        async def aclose(self):
            raise RuntimeError("http close failed")

    limiter = FakeRateLimiter()
    client = WBClient(
        make_token(),
        http_client=FailingCloseClient(),  # type: ignore[arg-type]
        rate_limiter=limiter,
    )

    with pytest.raises(RuntimeError, match="http close failed"):
        await client.aclose()

    assert limiter.closed is True
