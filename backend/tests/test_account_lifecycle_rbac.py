from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Response

from handlers.control_panel import users as control_panel_users


def _request(*roles: str):
    return SimpleNamespace(state=SimpleNamespace(roles=set(roles)))


def _target(*roles: str):
    return SimpleNamespace(
        roles=[SimpleNamespace(role=role) for role in roles]
    )


def test_admin_cannot_mutate_super_admin_lifecycle():
    assert control_panel_users._can_manage_sensitive_target(
        _request("admin"),
        _target("super_admin"),
    ) is False


def test_super_admin_can_mutate_super_admin_lifecycle():
    assert control_panel_users._can_manage_sensitive_target(
        _request("super_admin"),
        _target("super_admin"),
    ) is True


def test_admin_can_mutate_regular_user_lifecycle():
    assert control_panel_users._can_manage_sensitive_target(
        _request("admin"),
        _target("user"),
    ) is True



@pytest.mark.asyncio
async def test_admin_cannot_deactivate_super_admin_through_control_panel(monkeypatch):
    target_id = UUID("22222222-2222-4222-8222-222222222222")
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target = SimpleNamespace(
        id=target_id,
        roles=[SimpleNamespace(role="super_admin")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_deactivate(*_args, **_kwargs):
        raise AssertionError("admin must not deactivate super_admin")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "deactivate_account", must_not_deactivate)

    request = SimpleNamespace(
        state=SimpleNamespace(user_id=actor_id, roles={"admin"})
    )
    response = Response()
    result = await control_panel_users.remove_user(
        target_id,
        request,
        response,
        object(),
    )

    assert response.status_code == 403
    assert result["error"]["code"] == "SUPER_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_control_panel_rejects_self_deactivation_and_uses_account_flow(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target = SimpleNamespace(
        id=actor_id,
        roles=[SimpleNamespace(role="super_admin")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_deactivate(*_args, **_kwargs):
        raise AssertionError("control panel must not self-deactivate current operator")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "deactivate_account", must_not_deactivate)

    request = SimpleNamespace(
        state=SimpleNamespace(user_id=actor_id, roles={"super_admin"})
    )
    response = Response()
    result = await control_panel_users.remove_user(
        actor_id,
        request,
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "SELF_DEACTIVATION_USE_ACCOUNT_FLOW"
