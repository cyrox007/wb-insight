from datetime import datetime, timedelta, timezone

import httpx
import pytest

from integrations.wildberries.token_metadata import (
    WBTokenMetadata,
    WBTokenValidationError,
)
from integrations.wildberries.token_validation import validate_wb_token_live


def metadata(token_type: str = "base") -> WBTokenMetadata:
    return WBTokenMetadata(
        token_type=token_type,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        token_id="token-id",
        seller_id="seller-id",
        permissions_mask=0,
        service_id="service-42" if token_type == "service" else None,
        is_test=False,
    )


@pytest.mark.asyncio
async def test_base_token_ping_uses_bearer_only():
    async def handler(request: httpx.Request):
        assert request.url.path == "/ping"
        assert request.headers["Authorization"] == "Bearer raw-token"
        assert "X-Client-Secret" not in request.headers
        return httpx.Response(200, json={"Status": "OK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await validate_wb_token_live(
            "raw-token",
            metadata("base"),
            http_client=client,
        )


@pytest.mark.asyncio
async def test_service_token_ping_includes_client_secret():
    async def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer service-token"
        assert request.headers["X-Client-Secret"] == "service-secret"
        return httpx.Response(200, json={"Status": "OK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await validate_wb_token_live(
            "service-token",
            metadata("service"),
            service_secret="service-secret",
            http_client=client,
        )


@pytest.mark.asyncio
async def test_revoked_or_invalid_token_is_rejected():
    async def handler(_request: httpx.Request):
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WBTokenValidationError) as exc_info:
            await validate_wb_token_live(
                "bad-token",
                metadata("base"),
                http_client=client,
            )

    assert exc_info.value.code == "WB_TOKEN_REJECTED"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_wb_validation_outage_is_retryable_for_user():
    async def handler(request: httpx.Request):
        raise httpx.ConnectError("temporary failure", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WBTokenValidationError) as exc_info:
            await validate_wb_token_live(
                "raw-token",
                metadata("base"),
                http_client=client,
            )

    assert exc_info.value.code == "WB_TOKEN_VALIDATION_UNAVAILABLE"
    assert exc_info.value.status_code == 503
