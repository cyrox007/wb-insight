from models.account_lifecycle import AccountLifecycleEvent
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



class DeleteRequest:
    def __init__(self, actor_id, roles, payload):
        self.state = SimpleNamespace(user_id=actor_id, roles=set(roles))
        self._payload = payload

    async def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_admin_can_permanently_delete_inactive_regular_user(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target_id = UUID("22222222-2222-4222-8222-222222222222")
    target = SimpleNamespace(
        id=target_id,
        email="seller@example.com",
        is_active=False,
        is_staff=False,
        roles=[SimpleNamespace(role="user")],
    )
    calls = []

    async def fake_get_user(_session, _user_id):
        return target

    async def fake_record_event(_session, **kwargs):
        calls.append(("event", kwargs))
        return SimpleNamespace(id=UUID("33333333-3333-4333-8333-333333333333"))

    async def fake_delete_user(_session, user):
        calls.append(("delete", user.id))
        return True

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "record_lifecycle_event", fake_record_event)
    monkeypatch.setattr(control_panel_users, "delete_user", fake_delete_user)

    response = Response()
    result = await control_panel_users.permanently_delete_user(
        target_id,
        DeleteRequest(
            actor_id,
            {"admin"},
            {
                "confirm_email": "seller@example.com",
                "reason": "Дубликат тестового аккаунта",
            },
        ),
        response,
        object(),
    )

    assert result["status"] == "success"
    assert result["deleted"] is True
    assert result["user_id"] == str(target_id)
    assert calls[0][0] == "event"
    assert calls[0][1]["event_type"] == "account_permanently_deleted"
    assert calls[0][1]["event_data"]["deleted_user_id"] == str(target_id)
    assert calls[1] == ("delete", target_id)


@pytest.mark.asyncio
async def test_permanent_delete_requires_inactive_account(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target_id = UUID("22222222-2222-4222-8222-222222222222")
    target = SimpleNamespace(
        id=target_id,
        email="seller@example.com",
        is_active=True,
        is_staff=False,
        roles=[SimpleNamespace(role="user")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_delete(*_args, **_kwargs):
        raise AssertionError("Активный аккаунт нельзя удалить навсегда")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "delete_user", must_not_delete)

    response = Response()
    result = await control_panel_users.permanently_delete_user(
        target_id,
        DeleteRequest(
            actor_id,
            {"admin"},
            {"confirm_email": "seller@example.com"},
        ),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "USER_MUST_BE_INACTIVE"


@pytest.mark.asyncio
async def test_permanent_delete_rejects_wrong_email_confirmation(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target_id = UUID("22222222-2222-4222-8222-222222222222")
    target = SimpleNamespace(
        id=target_id,
        email="seller@example.com",
        is_active=False,
        is_staff=False,
        roles=[SimpleNamespace(role="user")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_delete(*_args, **_kwargs):
        raise AssertionError("Несовпадающее подтверждение не должно удалять пользователя")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "delete_user", must_not_delete)

    response = Response()
    result = await control_panel_users.permanently_delete_user(
        target_id,
        DeleteRequest(
            actor_id,
            {"admin"},
            {"confirm_email": "other@example.com"},
        ),
        response,
        object(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "USER_DELETE_CONFIRMATION_MISMATCH"


@pytest.mark.asyncio
async def test_admin_cannot_permanently_delete_super_admin(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target_id = UUID("22222222-2222-4222-8222-222222222222")
    target = SimpleNamespace(
        id=target_id,
        email="root@example.com",
        is_active=False,
        is_staff=True,
        roles=[SimpleNamespace(role="super_admin")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_delete(*_args, **_kwargs):
        raise AssertionError("admin не должен удалять super_admin")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "delete_user", must_not_delete)

    response = Response()
    result = await control_panel_users.permanently_delete_user(
        target_id,
        DeleteRequest(
            actor_id,
            {"admin"},
            {"confirm_email": "root@example.com"},
        ),
        response,
        object(),
    )

    assert response.status_code == 403
    assert result["error"]["code"] == "SUPER_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_permanent_delete_rejects_self_delete(monkeypatch):
    actor_id = UUID("11111111-1111-4111-8111-111111111111")
    target = SimpleNamespace(
        id=actor_id,
        email="admin@example.com",
        is_active=False,
        is_staff=True,
        roles=[SimpleNamespace(role="admin")],
    )

    async def fake_get_user(_session, _user_id):
        return target

    async def must_not_delete(*_args, **_kwargs):
        raise AssertionError("Нельзя удалить текущего оператора")

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(control_panel_users, "delete_user", must_not_delete)

    response = Response()
    result = await control_panel_users.permanently_delete_user(
        actor_id,
        DeleteRequest(
            actor_id,
            {"admin"},
            {"confirm_email": "admin@example.com"},
        ),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "SELF_DELETE_FORBIDDEN"



def test_permanent_delete_lifecycle_evidence_survives_user_removal():
    user_fk = next(iter(AccountLifecycleEvent.__table__.c.user_id.foreign_keys))
    actor_fk = next(iter(AccountLifecycleEvent.__table__.c.actor_user_id.foreign_keys))

    assert user_fk.ondelete == "SET NULL"
    assert actor_fk.ondelete == "SET NULL"
