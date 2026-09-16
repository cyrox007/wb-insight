from enum import Enum
from typing import Iterable

from models.users_model import UserRole


class Permission(str, Enum):
    """Application permissions derived directly from system roles.

    There is deliberately no permissions table and no role_permissions join
    table. Roles are the source of truth and each role has a fixed capability
    set defined in code.
    """

    CONTROL_PANEL_ACCESS = "control_panel:access"
    SYSTEM_MANAGE = "system:manage"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
    TARIFFS_READ = "tariffs:read"
    TARIFFS_WRITE = "tariffs:write"
    PAYMENTS_READ = "payments:read"
    PAYMENTS_WRITE = "payments:write"


_ALL_CONTROL_PANEL_PERMISSIONS = frozenset(Permission)

_ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.SUPER_ADMIN: _ALL_CONTROL_PANEL_PERMISSIONS,
    UserRole.ADMIN: frozenset(
        {
            Permission.CONTROL_PANEL_ACCESS,
            Permission.USERS_READ,
            Permission.USERS_WRITE,
            Permission.ROLES_READ,
            Permission.TARIFFS_READ,
            Permission.TARIFFS_WRITE,
            Permission.PAYMENTS_READ,
        }
    ),
    # Preserve the current product policy: only admin and super_admin may open
    # the control panel. Other roles can receive dashboard-level permissions
    # later without introducing database permission entities.
    UserRole.MANAGER: frozenset(),
    UserRole.SUPPORT: frozenset(),
    UserRole.ANALYST: frozenset(),
    UserRole.USER: frozenset(),
}


def permissions_for_role(role: UserRole | str) -> frozenset[Permission]:
    """Return the fixed permissions assigned to a role code."""
    try:
        normalized_role = role if isinstance(role, UserRole) else UserRole(str(role))
    except ValueError:
        return frozenset()
    return _ROLE_PERMISSIONS.get(normalized_role, frozenset())


def permissions_for_roles(roles: Iterable[UserRole | str]) -> frozenset[Permission]:
    """Return the union of permissions for all roles assigned to a user."""
    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(permissions_for_role(role))
    return frozenset(permissions)


def has_permission(roles: Iterable[UserRole | str], permission: Permission) -> bool:
    return permission in permissions_for_roles(roles)
