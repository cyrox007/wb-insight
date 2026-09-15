from types import SimpleNamespace

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
