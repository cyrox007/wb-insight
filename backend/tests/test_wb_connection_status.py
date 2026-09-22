from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from handlers.dashboard.profile_handler import (
    _public_token,
    _token_connection_status,
)
from models.tokens_model import Marketplace


def _token(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "label": "Основной кабинет",
        "marketplace": Marketplace.WILDBERRIES,
        "token_type": "service",
        "external_account_id": "seller-1",
        "issued_at": now,
        "expires_at": now + timedelta(days=30),
        "is_active": True,
        "is_revoked": False,
        "is_valid": True,
        "encrypted_token": "секрет-не-должен-попасть-в-ответ",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_connection_status_is_active_for_available_credential():
    token = _token()
    assert _token_connection_status(token, dashboard_available=True) == "active"


def test_connection_status_distinguishes_revoked_expired_and_inactive():
    assert _token_connection_status(
        _token(is_revoked=True, is_valid=False),
        dashboard_available=False,
    ) == "revoked"
    assert _token_connection_status(
        _token(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            is_valid=False,
        ),
        dashboard_available=False,
    ) == "expired"
    assert _token_connection_status(
        _token(is_active=False, is_valid=False),
        dashboard_available=False,
    ) == "inactive"


def test_connection_status_marks_valid_account_outside_tariff():
    token = _token()
    assert _token_connection_status(
        token,
        dashboard_available=False,
    ) == "outside_tariff"


def test_public_token_exposes_safe_status_without_secret():
    token = _token()
    result = _public_token(token, dashboard_available=False)

    assert result["connection_status"] == "outside_tariff"
    assert result["dashboard_available"] is False
    assert result["is_valid"] is True
    assert "encrypted_token" not in result
