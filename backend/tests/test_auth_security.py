from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from core.dependencies import _authorize_control_panel
from core.middleware import auth_middle
from utils.jwt import create_access_token, create_refresh_token


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
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/dashboard", token)

    await auth_middle(request)

    assert request.state.user["type"] == "access"


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_as_access_token():
    token = create_refresh_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/dashboard", token)

    with pytest.raises(HTTPException) as exc_info:
        await auth_middle(request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_open_control_panel():
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/control-panel/users", token)

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("user"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "admin_required"


@pytest.mark.asyncio
async def test_admin_can_open_control_panel():
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/control-panel/users", token)

    await _authorize_control_panel(request, _FakeSession("admin"))

    assert "admin" in request.state.roles


@pytest.mark.asyncio
async def test_admin_cannot_mutate_roles():
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/control-panel/roles", token, method="POST")

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(request, _FakeSession("admin"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "super_admin_required"


@pytest.mark.asyncio
async def test_super_admin_can_mutate_roles():
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/control-panel/roles", token, method="POST")

    await _authorize_control_panel(request, _FakeSession("super_admin"))

    assert "super_admin" in request.state.roles


@pytest.mark.asyncio
async def test_inactive_admin_is_rejected():
    token = create_access_token({"sub": "9da81db8-b89f-4aaf-9d9f-087c48b64e3c"})
    request = _request("/control-panel/users", token)

    with pytest.raises(HTTPException) as exc_info:
        await _authorize_control_panel(
            request,
            _FakeSession("admin", is_active=False),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "user_inactive"
