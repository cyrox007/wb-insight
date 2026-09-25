from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response

from handlers.control_panel import roles as role_handler
from models.users_model import UserRole


class RequestStub:
    def __init__(self, payload, actor_user_id=None):
        self._payload = payload
        self.state = SimpleNamespace(
            user_id=str(actor_user_id or uuid4()),
            permissions={"roles:write"},
        )

    async def json(self):
        return self._payload


def test_super_admin_confirmation_helper_requires_exact_target_email():
    assert role_handler._super_admin_confirmation_matches(
        UserRole.SUPER_ADMIN.value,
        "Admin@Example.com",
        "admin@example.com",
    )
    assert not role_handler._super_admin_confirmation_matches(
        UserRole.SUPER_ADMIN.value,
        "",
        "admin@example.com",
    )
    assert not role_handler._super_admin_confirmation_matches(
        UserRole.SUPER_ADMIN.value,
        "other@example.com",
        "admin@example.com",
    )
    assert role_handler._super_admin_confirmation_matches(
        UserRole.ADMIN.value,
        None,
        "admin@example.com",
    )


@pytest.mark.asyncio
async def test_super_admin_assignment_rejected_without_email_confirmation(monkeypatch):
    target_id = uuid4()
    target = SimpleNamespace(id=target_id, email="target@example.com")

    async def fake_get_user(_session, user_id):
        assert user_id == target_id
        return target

    async def unexpected_existing(*_args, **_kwargs):
        raise AssertionError("Проверка существующей роли не должна запускаться до подтверждения")

    monkeypatch.setattr(role_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(
        role_handler,
        "get_user_role_association_by_code",
        unexpected_existing,
    )

    response = Response()
    result = await role_handler.create_role(
        request=RequestStub({
            "user_id": str(target_id),
            "role": "super_admin",
        }),
        response=response,
        db_session=object(),
    )

    assert response.status_code == 400
    assert result["status"] == "error"
    assert result["error"]["code"] == "SUPER_ADMIN_CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_regular_role_assignment_does_not_require_email_confirmation(monkeypatch):
    target_id = uuid4()
    actor_id = uuid4()
    target = SimpleNamespace(id=target_id, email="target@example.com")
    created = {}

    async def fake_get_user(_session, _user_id):
        return target

    async def fake_existing(*_args, **_kwargs):
        return None

    async def fake_create_role(*, session, user_id, role_code, assigned_by):
        created.update({
            "user_id": user_id,
            "role_code": role_code,
            "assigned_by": assigned_by,
        })

    monkeypatch.setattr(role_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(
        role_handler,
        "get_user_role_association_by_code",
        fake_existing,
    )
    monkeypatch.setattr(
        role_handler,
        "create_user_role_association",
        fake_create_role,
    )

    response = Response()
    result = await role_handler.create_role(
        request=RequestStub({
            "user_id": str(target_id),
            "role": "admin",
        }, actor_id),
        response=response,
        db_session=object(),
    )

    assert result["status"] == "success"
    assert created == {
        "user_id": str(target_id),
        "role_code": "admin",
        "assigned_by": str(actor_id),
    }
