from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Response
from starlette.requests import Request

from handlers import session_handler
from services.session_identity import session_user_payload
from settings import config
from utils.jwt import create_refresh_token, verify_token


USER_ID = UUID("9da81db8-b89f-4aaf-9d9f-087c48b64e3c")


def _refresh_request(token: str) -> Request:
    cookie = f"{config.REFRESH_COOKIE_NAME}={token}".encode()
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/auth/refresh",
            "raw_path": b"/auth/refresh",
            "query_string": b"",
            "headers": [(b"cookie", cookie)],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 443),
        }
    )


def _user(session_version: int = 3):
    return SimpleNamespace(
        id=USER_ID,
        email="seller@example.com",
        full_name="Seller",
        is_active=True,
        session_version=session_version,
        hashed_password="must-never-leak",
        roles=[SimpleNamespace(role="user")],
    )


def test_session_user_payload_is_minimal_and_safe():
    payload = session_user_payload(_user())

    assert payload == {
        "id": str(USER_ID),
        "email": "seller@example.com",
        "full_name": "Seller",
        "tariff": None,
        "roles": ["user"],
    }
    assert "hashed_password" not in payload
    assert "session_version" not in payload


@pytest.mark.asyncio
async def test_refresh_restores_access_token_and_user_identity(monkeypatch):
    async def fake_get_user(_session, user_id):
        assert user_id == USER_ID
        return _user(session_version=3)

    monkeypatch.setattr(session_handler, "get_user_by_uuid", fake_get_user)

    refresh_token = create_refresh_token(
        {"sub": str(USER_ID), "email": "seller@example.com", "sv": 3}
    )
    request = _refresh_request(refresh_token)
    response = Response()

    payload = await session_handler.refresh_session(request, response, None)

    assert payload["status"] == "success"
    assert payload["user"]["id"] == str(USER_ID)
    assert payload["user"]["roles"] == ["user"]
    assert "hashed_password" not in payload["user"]

    access_payload = verify_token(payload["access_token"])
    assert access_payload is not None
    assert access_payload["type"] == "access"
    assert access_payload["sub"] == str(USER_ID)
    assert access_payload["sv"] == 3

    set_cookie = response.headers["set-cookie"].lower()
    assert config.REFRESH_COOKIE_NAME.lower() in set_cookie
    assert "httponly" in set_cookie
    assert "path=/" in set_cookie


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_session_version(monkeypatch):
    async def fake_get_user(_session, _user_id):
        return _user(session_version=4)

    monkeypatch.setattr(session_handler, "get_user_by_uuid", fake_get_user)

    refresh_token = create_refresh_token(
        {"sub": str(USER_ID), "email": "seller@example.com", "sv": 3}
    )
    response = Response()
    payload = await session_handler.refresh_session(
        _refresh_request(refresh_token),
        response,
        None,
    )

    assert response.status_code == 401
    assert payload["error"]["code"] == "SESSION_REVOKED"
    assert "max-age=0" in response.headers["set-cookie"].lower()
