import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from models.tokens_model import APIToken, Marketplace, TokenTypeWB
from services import token_services


class FakeSession:
    def __init__(self):
        self.added = []
        self.flushed = False

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True


def make_wb_token(payload: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.signature"


def permission_mask(*bits: int) -> int:
    return sum(1 << bit for bit in bits)


def test_non_expiring_marketplace_credential_is_valid_until_revoked():
    credential = APIToken(
        user_id=uuid4(),
        marketplace=Marketplace.OZON,
        token_type="api_key",
        external_account_id="123456",
        encrypted_token="encrypted-api-key",
        expires_at=None,
        is_active=True,
        is_revoked=False,
    )

    assert credential.is_expired is False
    assert credential.is_valid is True

    credential.is_revoked = True
    assert credential.is_valid is False


def test_wb_enum_matches_current_documented_claim_values():
    assert TokenTypeWB.BASE.value == "base"
    assert TokenTypeWB.TEST.value == "test"
    assert TokenTypeWB.PERSONAL.value == "personal"
    assert TokenTypeWB.SERVICE.value == "service"


@pytest.mark.asyncio
async def test_wb_insert_persists_seller_id_as_external_account_id(monkeypatch):
    now = datetime.now(timezone.utc)
    raw_token = make_wb_token(
        {
            "acc": 1,
            "exp": int((now + timedelta(days=30)).timestamp()),
            "sid": 987654,
            "s": permission_mask(1, 2, 3, 5, 6, 13, 30),
            "t": False,
        }
    )
    session = FakeSession()
    monkeypatch.setattr(
        token_services,
        "encrypt_token",
        lambda raw, user_id: f"encrypted:{user_id}:{len(raw)}",
    )
    monkeypatch.setattr(token_services.config, "WB_SERVICE_ID", "test-service")
    monkeypatch.setattr(token_services.config, "WB_SERVICE_SECRET", "test-secret")

    live_checks = []

    async def fake_live_check(raw, metadata, *, service_secret=None):
        live_checks.append((raw, metadata.token_type, service_secret))

    monkeypatch.setattr(token_services, "validate_wb_token_live", fake_live_check)

    user_id = uuid4()
    credential = await token_services.insert_token(
        session=session,  # type: ignore[arg-type]
        user_id=user_id,
        raw_token=raw_token,
        label="Main WB",
    )

    assert credential is not None
    assert credential.marketplace == Marketplace.WILDBERRIES
    assert credential.token_type == "base"
    assert credential.external_account_id == "987654"
    assert credential.expires_at is not None
    assert session.added == [credential]
    assert session.flushed is True
    assert live_checks == [(raw_token, "base", "test-secret")]
