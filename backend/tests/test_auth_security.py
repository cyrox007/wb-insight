from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from core.dependencies import _authorize_control_panel
from core.middleware import auth_middle
from core.session_cookie import clear_refresh_cookie, set_refresh_cookie
from core.session_security import SessionSecurityMiddleware
from settings import config
from utils.jwt import create_access_token, create_refresh_token


USER_ID = "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"


def _request(path: str, token: str, method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("test", 1234),
            "server": ("test", 80),
        }
    )


class _FakeResult:
    def __init__(self, role: str, is_active: bool = True):
        self._rows = [SimpleNamespace(role=role, is_active=is_active)]

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, role: str, is_active: bool = True):
        self.role = role
        self.is_active = is_active

    async def execute(self, _statement):
        return _FakeResult(self.role, self.is_active)


@pytest.mark.asyncio
async def test_access_token_is_accepted_by_auth_middleware():
    token = create_access_token({"sub": USER_ID})
    request = _request("/dashboard", token)

    await auth_middle(request)

    assert request.state.user["type"] == "access"


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_as_access_token():
    token = create_refresh_token({"sub": USER_ID})
    request = _request("/dashboard", token)

    with pytest.raises(HTTPException) as exc_info:
        await auth_middle(request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_open_control_panel():
    token = create_access_token({"sub": USER_ID})
    request = _request("/control-panel/users", token)

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("user"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "admin_required"


@pytest.mark.asyncio
async def test_manager_can_read_users_but_cannot_mutate_them():
    token = create_access_token({"sub": USER_ID})

    read_request = _request("/control-panel/users", token)
    await _authorize_control_panel(read_request, _FakeSession("manager"))
    assert "manager" in read_request.state.roles

    write_request = _request(
        f"/control-panel/users/{USER_ID}",
        token,
        method="PUT",
    )
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(write_request, _FakeSession("manager"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_support_can_read_users_but_cannot_mutate_them():
    token = create_access_token({"sub": USER_ID})

    read_request = _request("/control-panel/users", token)
    await _authorize_control_panel(read_request, _FakeSession("support"))

    write_request = _request(
        f"/control-panel/users/{USER_ID}",
        token,
        method="PUT",
    )
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(write_request, _FakeSession("support"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_analyst_can_open_staff_control_panel_overview_but_not_user_list():
    token = create_access_token({"sub": USER_ID})

    overview_request = _request("/control-panel/", token)
    await _authorize_control_panel(overview_request, _FakeSession("analyst"))

    users_request = _request("/control-panel/users", token)
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(users_request, _FakeSession("analyst"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_open_control_panel():
    token = create_access_token({"sub": USER_ID})
    request = _request("/control-panel/users", token)

    await _authorize_control_panel(request, _FakeSession("admin"))

    assert "admin" in request.state.roles


@pytest.mark.asyncio
async def test_admin_cannot_mutate_roles():
    token = create_access_token({"sub": USER_ID})
    request = _request("/control-panel/roles", token, method="POST")

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("admin"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "super_admin_required"


@pytest.mark.asyncio
async def test_super_admin_can_mutate_roles():
    token = create_access_token({"sub": USER_ID})
    request = _request("/control-panel/roles", token, method="POST")

    await _authorize_control_panel(request, _FakeSession("super_admin"))

    assert "super_admin" in request.state.roles


@pytest.mark.asyncio
async def test_inactive_admin_is_rejected():
    token = create_access_token({"sub": USER_ID})
    request = _request("/control-panel/users", token)

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(
            request,
            _FakeSession("admin", is_active=False),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "user_inactive"


@pytest.mark.asyncio
async def test_admin_cannot_delete_own_account():
    token = create_access_token({"sub": USER_ID})
    request = _request(f"/control-panel/users/{USER_ID}", token, method="DELETE")

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("admin"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_type"] == "self_account_deactivation"


@pytest.mark.asyncio
async def test_super_admin_cannot_remove_own_super_admin_role():
    token = create_access_token({"sub": USER_ID})
    request = _request(
        f"/control-panel/roles/{USER_ID}/super_admin",
        token,
        method="DELETE",
    )

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("super_admin"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_type"] == "self_super_admin_removal"


def test_legacy_get_refresh_is_disabled():
    app = FastAPI()
    app.add_middleware(SessionSecurityMiddleware)

    @app.get("/auth/refresh")
    async def legacy_refresh():
        return {"status": "should-not-run"}

    client = TestClient(app)
    response = client.get("/auth/refresh")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_refresh_cookie_uses_production_scope_and_security_flags(monkeypatch):
    monkeypatch.setattr(config, "REFRESH_COOKIE_NAME", "refresh_token")
    monkeypatch.setattr(config, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    monkeypatch.setattr(config, "COOKIE_SAMESITE", "strict")
    monkeypatch.setattr(config, "COOKIE_DOMAIN", ".example.com")

    response = Response()
    set_refresh_cookie(response, "refresh-secret")
    header = response.headers["set-cookie"].lower()

    assert "refresh_token=refresh-secret" in header
    assert "httponly" in header
    assert "secure" in header
    assert "samesite=strict" in header
    assert "path=/" in header
    assert "domain=.example.com" in header
    assert "max-age=604800" in header


def test_refresh_cookie_clear_uses_same_root_scope(monkeypatch):
    monkeypatch.setattr(config, "REFRESH_COOKIE_NAME", "refresh_token")
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    monkeypatch.setattr(config, "COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(config, "COOKIE_DOMAIN", ".example.com")

    response = Response()
    clear_refresh_cookie(response)
    header = response.headers["set-cookie"].lower()

    assert "refresh_token=" in header
    assert "max-age=0" in header
    assert "path=/" in header
    assert "domain=.example.com" in header
    assert "secure" in header
    assert "httponly" in header


def test_application_has_only_post_refresh_route():
    from app import app

    refresh_contract = app.openapi()["paths"]["/auth/refresh"]

    assert "post" in refresh_contract
    assert "get" not in refresh_contract
