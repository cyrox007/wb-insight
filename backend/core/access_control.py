from enum import Enum
from typing import Iterable

from models.users_model import UserRole


class Permission(str, Enum):
    """Разрешения приложения, напрямую определяемые системными ролями."""

    CONTROL_PANEL_ACCESS = "control_panel:access"
    SYSTEM_MANAGE = "system:manage"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_DELETE = "users:delete"
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
    TARIFFS_READ = "tariffs:read"
    TARIFFS_WRITE = "tariffs:write"
    PAYMENTS_READ = "payments:read"
    PAYMENTS_WRITE = "payments:write"
    AUDIT_READ = "audit:read"
    MAIL_READ = "mail:read"
    MAIL_WRITE = "mail:write"


_ALL_CONTROL_PANEL_PERMISSIONS = frozenset(Permission)

_ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.SUPER_ADMIN: _ALL_CONTROL_PANEL_PERMISSIONS,
    UserRole.ADMIN: frozenset(
        {
            Permission.CONTROL_PANEL_ACCESS,
            Permission.USERS_READ,
            Permission.USERS_WRITE,
            Permission.USERS_DELETE,
            Permission.ROLES_READ,
            Permission.TARIFFS_READ,
            Permission.TARIFFS_WRITE,
            Permission.PAYMENTS_READ,
            Permission.AUDIT_READ,
            Permission.MAIL_READ,
        }
    ),
    # Сотрудники получают только минимально необходимый операционный доступ.
    # Клиентская аналитика остаётся вторичной рабочей областью, а основной
    # интерфейс сотрудников определяется их служебной ролью.
    UserRole.MANAGER: frozenset(
        {
            Permission.CONTROL_PANEL_ACCESS,
            Permission.USERS_READ,
            Permission.TARIFFS_READ,
            Permission.PAYMENTS_READ,
            Permission.MAIL_READ,
            Permission.AUDIT_READ,
        }
    ),
    UserRole.SUPPORT: frozenset(
        {
            Permission.CONTROL_PANEL_ACCESS,
            Permission.USERS_READ,
            Permission.AUDIT_READ,
        }
    ),
    UserRole.ANALYST: frozenset(
        {
            Permission.CONTROL_PANEL_ACCESS,
        }
    ),
    UserRole.USER: frozenset(),
}


def permissions_for_role(role: UserRole | str) -> frozenset[Permission]:
    try:
        normalized_role = role if isinstance(role, UserRole) else UserRole(str(role))
    except ValueError:
        return frozenset()
    return _ROLE_PERMISSIONS.get(normalized_role, frozenset())


def permissions_for_roles(roles: Iterable[UserRole | str]) -> frozenset[Permission]:
    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(permissions_for_role(role))
    return frozenset(permissions)


def has_permission(roles: Iterable[UserRole | str], permission: Permission) -> bool:
    return permission in permissions_for_roles(roles)
