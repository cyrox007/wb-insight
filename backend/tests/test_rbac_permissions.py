from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core import authorization
from core.access_control import Permission, permissions_for_role
from handlers.control_panel.audit import router as audit_router
from handlers.control_panel.home import router as home_router
from handlers.control_panel.mail import router as mail_router
from handlers.control_panel.operations import router as operations_router
from handlers.control_panel.payments import router as payments_router
from handlers.control_panel import roles as roles_handler
from handlers.control_panel.roles import router as roles_router
from handlers.control_panel.tariffs import router as tariffs_router
from handlers.control_panel.users import router as users_router
from models.users_model import UserRole


def _route_permissions(router, path: str, method: str) -> set[str]:
    method = method.upper()
    for route in router.routes:
        if getattr(route, "path", None) != path:
            continue
        if method not in set(getattr(route, "methods", set())):
            continue
        return {
            permission
            for dependency in route.dependant.dependencies
            if (
                permission := getattr(
                    dependency.call,
                    "required_permission",
                    None,
                )
            )
        }
    raise AssertionError(f"Route not found: {method} {path}")


def test_role_permission_matrix_is_explicit():
    super_permissions = permissions_for_role(UserRole.SUPER_ADMIN)
    admin_permissions = permissions_for_role(UserRole.ADMIN)

    assert set(super_permissions) == set(Permission)
    assert Permission.CONTROL_PANEL_ACCESS in admin_permissions
    assert Permission.USERS_WRITE in admin_permissions
    assert Permission.USERS_DELETE in admin_permissions
    assert Permission.TARIFFS_WRITE in admin_permissions
    assert Permission.ROLES_WRITE not in admin_permissions
    assert Permission.PAYMENTS_WRITE not in admin_permissions
    assert Permission.MAIL_WRITE not in admin_permissions
    assert Permission.SYSTEM_MANAGE not in admin_permissions

    manager_permissions = permissions_for_role(UserRole.MANAGER)
    assert {
        Permission.CONTROL_PANEL_ACCESS,
        Permission.USERS_READ,
        Permission.TARIFFS_READ,
        Permission.PAYMENTS_READ,
        Permission.MAIL_READ,
        Permission.AUDIT_READ,
    } <= set(manager_permissions)
    assert Permission.USERS_WRITE not in manager_permissions
    assert Permission.USERS_DELETE not in manager_permissions
    assert Permission.TARIFFS_WRITE not in manager_permissions
    assert Permission.PAYMENTS_WRITE not in manager_permissions
    assert Permission.MAIL_WRITE not in manager_permissions
    assert Permission.ROLES_WRITE not in manager_permissions

    support_permissions = permissions_for_role(UserRole.SUPPORT)
    assert set(support_permissions) == {
        Permission.CONTROL_PANEL_ACCESS,
        Permission.USERS_READ,
        Permission.AUDIT_READ,
    }

    analyst_permissions = permissions_for_role(UserRole.ANALYST)
    assert set(analyst_permissions) == {Permission.CONTROL_PANEL_ACCESS}

    assert permissions_for_role(UserRole.USER) == frozenset()


@pytest.mark.asyncio
async def test_require_permission_reads_current_database_roles(monkeypatch):
    async def fake_auth(_request):
        return None

    async def fake_roles(_request, _session):
        return {UserRole.ADMIN.value}

    monkeypatch.setattr(authorization, "auth_middle", fake_auth)
    monkeypatch.setattr(authorization, "_get_active_user_roles", fake_roles)

    request = SimpleNamespace(state=SimpleNamespace())
    dependency = authorization.require_permission(Permission.TARIFFS_WRITE)

    await dependency(request, object())

    assert Permission.TARIFFS_WRITE.value in request.state.permissions
    assert Permission.ROLES_WRITE.value not in request.state.permissions


@pytest.mark.asyncio
async def test_admin_cannot_escalate_roles_through_backend(monkeypatch):
    async def fake_auth(_request):
        return None

    async def fake_roles(_request, _session):
        return {UserRole.ADMIN.value}

    monkeypatch.setattr(authorization, "auth_middle", fake_auth)
    monkeypatch.setattr(authorization, "_get_active_user_roles", fake_roles)

    request = SimpleNamespace(state=SimpleNamespace())
    dependency = authorization.require_permission(Permission.ROLES_WRITE)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request, object())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_type"] == "permission_denied"
    assert exc_info.value.detail["required_permission"] == "roles:write"


@pytest.mark.asyncio
async def test_super_admin_can_manage_roles(monkeypatch):
    async def fake_auth(_request):
        return None

    async def fake_roles(_request, _session):
        return {UserRole.SUPER_ADMIN.value}

    monkeypatch.setattr(authorization, "auth_middle", fake_auth)
    monkeypatch.setattr(authorization, "_get_active_user_roles", fake_roles)

    request = SimpleNamespace(state=SimpleNamespace())
    dependency = authorization.require_permission(Permission.ROLES_WRITE)

    await dependency(request, object())

    assert Permission.ROLES_WRITE.value in request.state.permissions


def test_control_panel_routes_enforce_granular_permissions():
    assert _route_permissions(home_router, "/control-panel/", "GET") == {
        "control_panel:access"
    }

    assert _route_permissions(users_router, "/control-panel/users/", "GET") == {
        "users:read"
    }
    assert _route_permissions(users_router, "/control-panel/users/{user_uuid}", "PUT") == {
        "users:read",
        "users:write",
    }
    assert _route_permissions(users_router, "/control-panel/users/{user_uuid}", "DELETE") == {
        "users:read",
        "users:write",
    }
    assert _route_permissions(
        users_router,
        "/control-panel/users/{user_uuid}/purge",
        "DELETE",
    ) == {
        "users:read",
        "users:delete",
    }

    assert _route_permissions(
        users_router,
        "/control-panel/users/{user_uuid}/verify-email",
        "POST",
    ) == {
        "users:read",
        "users:write",
    }

    assert _route_permissions(roles_router, "/control-panel/roles/", "GET") == {
        "roles:read"
    }
    assert _route_permissions(roles_router, "/control-panel/roles/", "POST") == {
        "roles:read",
        "roles:write",
    }
    assert _route_permissions(
        roles_router,
        "/control-panel/roles/{user_id}/{role_code}",
        "DELETE",
    ) == {
        "roles:read",
        "roles:write",
    }

    assert _route_permissions(tariffs_router, "/control-panel/tariffs/", "GET") == {
        "tariffs:read"
    }
    assert _route_permissions(
        tariffs_router,
        "/control-panel/tariffs/create",
        "POST",
    ) == {
        "tariffs:read",
        "tariffs:write",
    }

    assert _route_permissions(
        payments_router,
        "/control-panel/payments/providers",
        "GET",
    ) == {
        "payments:read"
    }
    assert _route_permissions(
        payments_router,
        "/control-panel/payments/providers/{provider}/{mode}",
        "PUT",
    ) == {
        "payments:read",
        "payments:write",
    }

    assert _route_permissions(audit_router, "/control-panel/audit/", "GET") == {
        "audit:read"
    }

    assert _route_permissions(
        mail_router,
        "/control-panel/mail/campaigns",
        "GET",
    ) == {
        "mail:read"
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/campaigns",
        "POST",
    ) == {
        "mail:read",
        "mail:write",
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/campaigns/{campaign_id}/preview",
        "POST",
    ) == {
        "mail:read"
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/campaigns/{campaign_id}/launch",
        "POST",
    ) == {
        "mail:read",
        "mail:write",
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/gateway",
        "PUT",
    ) == {
        "mail:read",
        "mail:write",
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/gateway/test",
        "POST",
    ) == {
        "mail:read",
        "mail:write",
    }

    assert _route_permissions(
        mail_router,
        "/control-panel/mail/diagnostics/password-reset/{user_id}",
        "GET",
    ) == {
        "mail:read"
    }
    assert _route_permissions(
        mail_router,
        "/control-panel/mail/campaigns/{campaign_id}",
        "PUT",
    ) == {
        "mail:read",
        "mail:write",
    }

    assert _route_permissions(
        operations_router,
        "/control-panel/operations/health",
        "GET",
    ) == {
        "system:manage"
    }



class RoleRequestStub:
    def __init__(self, payload, actor_id="11111111-1111-4111-8111-111111111111"):
        self._payload = payload
        self.state = SimpleNamespace(
            user_id=actor_id,
            permissions={Permission.ROLES_WRITE.value},
        )

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.mark.asyncio
async def test_create_role_rejects_invalid_payload_before_database_calls(monkeypatch):
    async def must_not_call(*_args, **_kwargs):
        raise AssertionError("База данных не должна вызываться для некорректного payload")

    monkeypatch.setattr(roles_handler, "get_user_by_uuid", must_not_call)

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.create_role(
        RoleRequestStub({"user_id": "bad-id", "role": "admin"}),
        response,
        object(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "USER_ID_INVALID"


@pytest.mark.asyncio
async def test_create_role_rejects_unknown_role(monkeypatch):
    async def must_not_call(*_args, **_kwargs):
        raise AssertionError("Неизвестная роль не должна доходить до БД")

    monkeypatch.setattr(roles_handler, "get_user_by_uuid", must_not_call)

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.create_role(
        RoleRequestStub(
            {
                "user_id": "22222222-2222-4222-8222-222222222222",
                "role": "root_owner",
            }
        ),
        response,
        object(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "ROLE_INVALID"


@pytest.mark.asyncio
async def test_create_role_returns_not_found_for_missing_user(monkeypatch):
    async def missing_user(*_args, **_kwargs):
        return None

    monkeypatch.setattr(roles_handler, "get_user_by_uuid", missing_user)

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.create_role(
        RoleRequestStub(
            {
                "user_id": "22222222-2222-4222-8222-222222222222",
                "role": "admin",
            }
        ),
        response,
        object(),
    )

    assert response.status_code == 404
    assert result["error"]["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_role_returns_conflict_for_duplicate(monkeypatch):
    async def existing_user(*_args, **_kwargs):
        return object()

    async def existing_role(*_args, **_kwargs):
        return object()

    monkeypatch.setattr(roles_handler, "get_user_by_uuid", existing_user)
    monkeypatch.setattr(
        roles_handler,
        "get_user_role_association_by_code",
        existing_role,
    )

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.create_role(
        RoleRequestStub(
            {
                "user_id": "22222222-2222-4222-8222-222222222222",
                "role": "admin",
            }
        ),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "ROLE_ALREADY_ASSIGNED"


@pytest.mark.asyncio
async def test_super_admin_cannot_remove_own_super_admin_role(monkeypatch):
    target_id = "11111111-1111-4111-8111-111111111111"

    async def existing_role(*_args, **_kwargs):
        return object()

    async def must_not_lock(*_args, **_kwargs):
        raise AssertionError("Self-demotion должна блокироваться до удаления роли")

    monkeypatch.setattr(
        roles_handler,
        "get_user_role_association_by_code",
        existing_role,
    )
    monkeypatch.setattr(
        roles_handler,
        "get_role_associations_for_update",
        must_not_lock,
    )

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.remove_role(
        target_id,
        "super_admin",
        RoleRequestStub({}, actor_id=target_id),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "SELF_SUPER_ADMIN_REMOVAL_FORBIDDEN"


@pytest.mark.asyncio
async def test_last_super_admin_role_cannot_be_removed(monkeypatch):
    target_id = "22222222-2222-4222-8222-222222222222"

    async def existing_role(*_args, **_kwargs):
        return object()

    async def one_super_admin(*_args, **_kwargs):
        return [object()]

    async def must_not_delete(*_args, **_kwargs):
        raise AssertionError("Последний super_admin не должен удаляться")

    monkeypatch.setattr(
        roles_handler,
        "get_user_role_association_by_code",
        existing_role,
    )
    monkeypatch.setattr(
        roles_handler,
        "get_role_associations_for_update",
        one_super_admin,
    )
    monkeypatch.setattr(
        roles_handler,
        "delete_role_association",
        must_not_delete,
    )

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.remove_role(
        target_id,
        "super_admin",
        RoleRequestStub({}),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "LAST_SUPER_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_super_admin_role_can_be_removed_when_another_one_remains(monkeypatch):
    target_id = "22222222-2222-4222-8222-222222222222"
    target_role = object()
    deleted = []

    async def existing_role(*_args, **_kwargs):
        return target_role

    async def two_super_admins(*_args, **_kwargs):
        return [object(), object()]

    async def delete_role(*_args, **kwargs):
        deleted.append(kwargs["target_role"])
        return True

    monkeypatch.setattr(
        roles_handler,
        "get_user_role_association_by_code",
        existing_role,
    )
    monkeypatch.setattr(
        roles_handler,
        "get_role_associations_for_update",
        two_super_admins,
    )
    monkeypatch.setattr(
        roles_handler,
        "delete_role_association",
        delete_role,
    )

    response = SimpleNamespace(status_code=200)
    result = await roles_handler.remove_role(
        target_id,
        "super_admin",
        RoleRequestStub({}),
        response,
        object(),
    )

    assert result["status"] == "success"
    assert result["code"] == "ROLE_DELETED"
    assert deleted == [target_role]
