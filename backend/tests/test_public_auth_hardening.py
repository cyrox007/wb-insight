import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

import core.auth_security as auth_security
import services.auth_rate_limit_service as rate_limit
from core.auth_security import PublicAuthSecurityMiddleware
from handlers.session_handler import logout
from services.auth_rate_limit_service import RateLimitDecision
from settings import config
from utils.jwt import create_access_token, create_refresh_token


USER_ID = "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"


async def _allowed_limit(*_args, **_kwargs):
    return RateLimitDecision(allowed=True)


def _request(
    path: str,
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] = ("203.0.113.10", 1234),
) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": client,
            "server": ("test", 443),
        }
    )


def test_public_identity_check_is_neutral_and_does_not_call_leaky_route(monkeypatch):
    monkeypatch.setattr(auth_security, "check_auth_rate_limit", _allowed_limit)
    called = {"value": False}
    app = FastAPI()
    app.add_middleware(PublicAuthSecurityMiddleware)

    @app.post("/auth/check-email")
    async def leaky_check():
        called["value"] = True
        return {"status": "error", "available": False}

    response = TestClient(app).post(
        "/auth/check-email",
        json={"email": "seller@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["checked"] is True
    assert "available" not in response.json()
    assert called["value"] is False


def test_public_identity_check_keeps_format_validation(monkeypatch):
    monkeypatch.setattr(auth_security, "check_auth_rate_limit", _allowed_limit)
    app = FastAPI()
    app.add_middleware(PublicAuthSecurityMiddleware)

    @app.post("/auth/check-email")
    async def check_email():
        return {"status": "should-not-run"}

    response = TestClient(app).post(
        "/auth/check-email",
        json={"email": "not-an-email"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMAIL_INVALID"


def test_login_rate_limit_returns_429_and_retry_after(monkeypatch):
    async def denied(*_args, **_kwargs):
        return RateLimitDecision(allowed=False, retry_after_seconds=37)

    monkeypatch.setattr(auth_security, "check_auth_rate_limit", denied)
    app = FastAPI()
    app.add_middleware(PublicAuthSecurityMiddleware)

    @app.post("/auth/login")
    async def login_route():
        return {"status": "should-not-run"}

    response = TestClient(app).post(
        "/auth/login",
        json={"email": "seller@example.com", "password": "secret"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.json()["error"]["code"] == "AUTH_RATE_LIMITED"
    assert response.json()["error"]["details"]["retry_after_seconds"] == 37


def test_login_guard_preserves_request_body_for_handler(monkeypatch):
    monkeypatch.setattr(auth_security, "check_auth_rate_limit", _allowed_limit)
    app = FastAPI()
    app.add_middleware(PublicAuthSecurityMiddleware)

    @app.post("/auth/login")
    async def login_route(request: Request):
        payload = await request.json()
        return {"status": "success", "email": payload["email"]}

    response = TestClient(app).post(
        "/auth/login",
        json={"email": "seller@example.com", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "seller@example.com"


def test_rate_limit_key_does_not_contain_personal_identifier():
    raw = "Seller@example.com"
    key = rate_limit._key("login", "identity", raw)

    assert raw.lower() not in key.lower()
    assert key == rate_limit._key("login", "identity", raw)
    assert key != rate_limit._key("login", "identity", "other@example.com")


def test_client_ip_trusts_x_real_ip_only_from_local_proxy():
    direct = _request(
        "/auth/login",
        headers=[(b"x-real-ip", b"198.51.100.25")],
        client=("203.0.113.10", 1234),
    )
    proxied = _request(
        "/auth/login",
        headers=[(b"x-real-ip", b"198.51.100.25")],
        client=("127.0.0.1", 1234),
    )

    assert rate_limit.client_ip(direct) == "203.0.113.10"
    assert rate_limit.client_ip(proxied) == "198.51.100.25"


class _LogoutSession:
    def __init__(self, rowcount: int = 1):
        self.rowcount = rowcount
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(rowcount=self.rowcount)


@pytest.mark.asyncio
async def test_logout_revokes_server_session_version_and_clears_cookie(monkeypatch):
    monkeypatch.setattr(config, "REFRESH_COOKIE_NAME", "refresh_token")
    token = create_refresh_token(
        {"sub": USER_ID, "email": "seller@example.com", "sv": 7}
    )
    request = _request(
        "/auth/logout",
        headers=[(b"cookie", f"refresh_token={token}".encode())],
    )
    response = Response()
    session = _LogoutSession(rowcount=1)

    result = await logout(request, response, session)

    assert result["status"] == "success"
    assert result["session_revoked"] is True
    assert "всех устройствах" in result["message"]
    assert "session_version" in str(session.statement)
    assert "refresh_token=" in response.headers["set-cookie"].lower()
    assert "max-age=0" in response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_logout_uses_access_token_when_refresh_cookie_is_missing():
    token = create_access_token(
        {"sub": USER_ID, "email": "seller@example.com", "sv": 3}
    )
    request = _request(
        "/auth/logout",
        headers=[(b"authorization", f"Bearer {token}".encode())],
    )
    response = Response()
    session = _LogoutSession(rowcount=1)

    result = await logout(request, response, session)

    assert result["session_revoked"] is True
    assert session.statement is not None


@pytest.mark.asyncio
async def test_logout_is_idempotent_for_already_revoked_session(monkeypatch):
    monkeypatch.setattr(config, "REFRESH_COOKIE_NAME", "refresh_token")
    token = create_refresh_token(
        {"sub": USER_ID, "email": "seller@example.com", "sv": 1}
    )
    request = _request(
        "/auth/logout",
        headers=[(b"cookie", f"refresh_token={token}".encode())],
    )
    response = Response()
    session = _LogoutSession(rowcount=0)

    result = await logout(request, response, session)

    assert result["status"] == "success"
    assert result["session_revoked"] is False
