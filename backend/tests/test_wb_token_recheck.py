from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.token_metadata import (
    WBTokenMetadata,
    WBTokenValidationError,
)
from models.tokens_model import Marketplace
from handlers.dashboard import token_handler
from services import token_services


class FakeSession:
    def __init__(self):
        self.flush_count = 0

    async def flush(self):
        self.flush_count += 1


def make_token():
    return SimpleNamespace(
        id=uuid4(),
        marketplace=Marketplace.WILDBERRIES,
        encrypted_token="зашифрованный-токен",
        token_type="base",
        external_account_id="seller-old",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=False,
        is_revoked=True,
    )


def make_metadata():
    return WBTokenMetadata(
        token_type="base",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        token_id="token-id",
        seller_id="seller-new",
        permissions_mask=0,
        service_id=None,
        is_test=False,
    )


def prepare_validation(monkeypatch, metadata):
    monkeypatch.setattr(
        token_services,
        "decrypt_token",
        lambda _encrypted, _user_id: "raw-token",
    )
    monkeypatch.setattr(
        token_services,
        "decode_wb_token",
        lambda _raw: metadata,
    )
    monkeypatch.setattr(
        token_services,
        "validate_cloud_service_token",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        token_services,
        "validate_analytics_permissions",
        lambda *_args, **_kwargs: None,
    )


@pytest.mark.asyncio
async def test_recheck_restores_confirmed_wb_connection(monkeypatch):
    session = FakeSession()
    token = make_token()
    metadata = make_metadata()
    prepare_validation(monkeypatch, metadata)

    async def valid_live_check(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        token_services,
        "validate_wb_token_live",
        valid_live_check,
    )

    result = await token_services.check_stored_wb_token(
        session=session,
        user_id=uuid4(),
        token=token,
    )

    assert result["valid"] is True
    assert result["connection_status"] == "active"
    assert token.is_active is True
    assert token.is_revoked is False
    assert token.external_account_id == "seller-new"
    assert token.expires_at == metadata.expires_at
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_recheck_marks_rejected_wb_connection_as_revoked(monkeypatch):
    session = FakeSession()
    token = make_token()
    token.is_active = True
    token.is_revoked = False
    prepare_validation(monkeypatch, make_metadata())

    async def rejected_live_check(*_args, **_kwargs):
        raise WBTokenValidationError(
            "WB_TOKEN_REJECTED",
            "Wildberries отклонил токен.",
        )

    monkeypatch.setattr(
        token_services,
        "validate_wb_token_live",
        rejected_live_check,
    )

    result = await token_services.check_stored_wb_token(
        session=session,
        user_id=uuid4(),
        token=token,
    )

    assert result["valid"] is False
    assert result["connection_status"] == "revoked"
    assert result["code"] == "WB_TOKEN_REJECTED"
    assert token.is_active is False
    assert token.is_revoked is True
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_recheck_does_not_change_state_on_temporary_wb_failure(monkeypatch):
    session = FakeSession()
    token = make_token()
    token.is_active = True
    token.is_revoked = False
    prepare_validation(monkeypatch, make_metadata())

    async def unavailable_live_check(*_args, **_kwargs):
        raise WBTokenValidationError(
            "WB_TOKEN_VALIDATION_UNAVAILABLE",
            "Wildberries временно недоступен для проверки токена.",
            status_code=503,
        )

    monkeypatch.setattr(
        token_services,
        "validate_wb_token_live",
        unavailable_live_check,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        await token_services.check_stored_wb_token(
            session=session,
            user_id=uuid4(),
            token=token,
        )

    assert exc_info.value.code == "WB_TOKEN_VALIDATION_UNAVAILABLE"
    assert token.is_active is True
    assert token.is_revoked is False
    assert session.flush_count == 0


def test_token_router_exposes_connection_recheck():
    routes = {
        (route.path, method)
        for route in token_handler.router.routes
        for method in route.methods
    }
    assert ("/dashboard/tokens/{token_id}/check", "POST") in routes
