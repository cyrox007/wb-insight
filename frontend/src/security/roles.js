const STAFF_ROLES = new Set(['super_admin', 'admin', 'manager', 'support', 'analyst'])
const CONTROL_PANEL_ROLES = new Set(['super_admin', 'admin', 'manager', 'support', 'analyst'])

export function roleCodes(user) {
  return Array.isArray(user?.roles) ? user.roles.filter(Boolean) : []
}

export function hasRole(user, role) {
  return roleCodes(user).includes(role)
}

export function isStaffUser(user) {
  return roleCodes(user).some((role) => STAFF_ROLES.has(role))
}

export function isClientOnlyUser(user) {
  return !isStaffUser(user)
}

export function canAccessControlPanel(user) {
  return roleCodes(user).some((role) => CONTROL_PANEL_ROLES.has(role))
}

export function defaultAuthenticatedRouteName(user) {
  return isStaffUser(user) ? 'staff.home' : 'dashboard.home'
}

export const ROLE_LABELS = {
  super_admin: 'Суперадмин',
  admin: 'Администратор',
  manager: 'Менеджер',
  support: 'Поддержка',
  analyst: 'Аналитик',
  user: 'Пользователь',
}
