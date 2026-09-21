<script setup>
import { computed, onMounted, ref } from 'vue'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import CP_Users from '@/API/ControlPanel/CP_Users'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'

const users = ref([])
const roles = ref([])
const permissions = ref([])
const canManageRoles = ref(false)
const selectedRoles = ref({})
const expandedUserId = ref('')
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionKey = ref('')
const removeConfirm = ref({ isOpen: false, user: null, role: '' })

const ROLE_LABELS = {
  super_admin: 'Суперадмин',
  admin: 'Администратор',
  manager: 'Менеджер',
  support: 'Поддержка',
  analyst: 'Аналитик',
  user: 'Пользователь',
}

const ROLE_DESCRIPTIONS = {
  super_admin: 'Полный системный доступ. Единственная роль, которая может изменять роли и критические настройки.',
  admin: 'Операционное администрирование пользователей и тарифов, просмотр платежей, аудита и рассылок.',
  manager: 'Зарезервированная операционная роль. Административные permissions пока не назначены.',
  support: 'Зарезервированная роль поддержки. Административные permissions пока не назначены.',
  analyst: 'Зарезервированная аналитическая роль. Административные permissions пока не назначены.',
  user: 'Базовая клиентская роль без доступа к панели управления.',
}

const PERMISSION_LABELS = {
  'control_panel:access': 'Доступ к панели управления',
  'system:manage': 'Системные настройки',
  'users:read': 'Пользователи · просмотр',
  'users:write': 'Пользователи · изменение',
  'roles:read': 'Роли · просмотр',
  'roles:write': 'Роли · изменение',
  'tariffs:read': 'Тарифы · просмотр',
  'tariffs:write': 'Тарифы · изменение',
  'payments:read': 'Платежи · просмотр',
  'payments:write': 'Платежи · настройка',
  'audit:read': 'Аудит · просмотр',
  'mail:read': 'Рассылки · просмотр',
  'mail:write': 'Рассылки · изменение и запуск',
}

const roleCodes = computed(() => roles.value.map((role) => role.code))
const roleLabel = (role) => ROLE_LABELS[role] || role
const permissionLabel = (permission) => PERMISSION_LABELS[permission] || permission
const roleByCode = (code) => roles.value.find((role) => role.code === code)
const rolePermissions = (code) => roleByCode(code)?.permissions || []
const hasRolePermission = (code, permission) => rolePermissions(code).includes(permission)
const userRoleCodes = (user) => (user.roles || []).map((role) => role.role)
const assignableRoles = (user) => roleCodes.value.filter((role) => !userRoleCodes(user).includes(role))
const isActing = computed(() => Boolean(actionKey.value))

function effectivePermissions(user) {
  if (Array.isArray(user.permissions)) return user.permissions
  const result = new Set()
  for (const role of userRoleCodes(user)) {
    for (const permission of rolePermissions(role)) result.add(permission)
  }
  return [...result].sort()
}

function toggleUserPermissions(userId) {
  expandedUserId.value = expandedUserId.value === userId ? '' : userId
}

async function loadData() {
  isLoading.value = true
  loadError.value = ''
  actionError.value = ''
  try {
    const [usersResponse, rolesResponse] = await Promise.all([
      CP_Users.getUserList(),
      CP_Roles.getRolesList(),
    ])
    if (usersResponse.data?.status !== 'success' || !Array.isArray(usersResponse.data?.user_list)) {
      throw new Error('Некорректный ответ API пользователей')
    }
    if (rolesResponse.data?.status !== 'success' || !Array.isArray(rolesResponse.data?.roles)) {
      throw new Error('Некорректный ответ API ролей')
    }

    users.value = usersResponse.data.user_list
    roles.value = rolesResponse.data.roles
    permissions.value = Array.isArray(rolesResponse.data.permissions) ? rolesResponse.data.permissions : []
    canManageRoles.value = Boolean(rolesResponse.data.can_manage)

    for (const user of users.value) {
      selectedRoles.value[user.id] = assignableRoles(user)[0] || ''
    }
  } catch (error) {
    console.error('Ошибка загрузки управления ролями:', error)
    loadError.value = error.response?.data?.error?.message || 'Не удалось загрузить пользователей и роли.'
  } finally {
    isLoading.value = false
  }
}

async function assignRole(user) {
  const role = selectedRoles.value[user.id]
  if (!role || !canManageRoles.value || isActing.value) return
  actionKey.value = `assign:${user.id}`
  actionError.value = ''
  try {
    const response = await CP_Roles.assignRoleToUser(user.id, role)
    if (response.data?.status !== 'success') {
      throw new Error(response.data?.error?.message || response.data?.message || 'Не удалось назначить роль')
    }
    await loadData()
  } catch (error) {
    console.error('Ошибка назначения роли:', error)
    actionError.value = error.response?.data?.error?.message || error.message || 'Не удалось назначить роль.'
  } finally {
    actionKey.value = ''
  }
}

function askRemoveRole(user, role) {
  if (!canManageRoles.value || role === 'user' || isActing.value) return
  removeConfirm.value = { isOpen: true, user, role }
}

function closeRemoveConfirm() {
  if (isActing.value) return
  removeConfirm.value = { isOpen: false, user: null, role: '' }
}

async function removeRoleConfirmed() {
  const user = removeConfirm.value.user
  const role = removeConfirm.value.role
  if (!user?.id || !role || !canManageRoles.value || isActing.value) return

  actionKey.value = `remove:${user.id}:${role}`
  actionError.value = ''
  try {
    const response = await CP_Roles.deleteRoleFromUser(user.id, role)
    if (response.data?.status !== 'success') {
      throw new Error(response.data?.error?.message || response.data?.message || 'Не удалось удалить роль')
    }
    removeConfirm.value = { isOpen: false, user: null, role: '' }
    await loadData()
  } catch (error) {
    console.error('Ошибка удаления роли:', error)
    actionError.value = error.response?.data?.error?.message || error.message || 'Не удалось удалить роль.'
  } finally {
    actionKey.value = ''
  }
}

onMounted(loadData)
</script>

<template>
  <section class="cp-page">
    <header class="cp-page-header">
      <div>
        <p class="cp-eyebrow">Доступ</p>
        <h2 class="cp-detail-title">Роли и права</h2>
        <p class="cp-subtitle">Роли назначаются пользователям, а их реальные permissions определяются и проверяются backend-ом.</p>
      </div>
    </header>

    <div class="cp-info-callout rbac-contract">
      <strong>Источник истины — backend RBAC.</strong>
      <span>Эта страница не «прячет кнопки вместо защиты»: каждый административный API endpoint повторно проверяет нужное permission по актуальным ролям из БД. Здесь можно увидеть матрицу и, при наличии <code>roles:write</code>, изменить назначения.</span>
    </div>

    <div v-if="isLoading" class="cp-state" role="status">Загружаем роли и права…</div>
    <div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
      <div class="cp-state__stack">
        <strong>{{ loadError }}</strong>
        <BaseButton variant="outline" size="small" text="Повторить" @click="loadData" />
      </div>
    </div>

    <template v-else>
      <section class="rbac-role-summary">
        <article v-for="role in roles" :key="role.code" class="cp-card rbac-role-card">
          <div class="rbac-role-card__head">
            <span class="cp-chip cp-chip--accent">{{ roleLabel(role.code) }}</span>
            <span class="cp-muted">{{ role.permissions.length }} прав</span>
          </div>
          <p class="cp-card-note">{{ ROLE_DESCRIPTIONS[role.code] || role.code }}</p>
          <div v-if="role.permissions.length" class="rbac-mini-permissions">
            <span v-for="permission in role.permissions.slice(0, 4)" :key="permission" class="rbac-mini-permission">
              {{ permissionLabel(permission) }}
            </span>
            <span v-if="role.permissions.length > 4" class="cp-muted">+{{ role.permissions.length - 4 }}</span>
          </div>
          <div v-else class="cp-muted">Административных permissions пока нет.</div>
        </article>
      </section>

      <section class="cp-card rbac-matrix-card">
        <div class="rbac-section-head">
          <div>
            <p class="cp-eyebrow">Матрица доступа</p>
            <h3 class="cp-detail-title rbac-section-title">Что реально разрешает каждая роль</h3>
          </div>
          <span class="cp-muted">{{ permissions.length }} permissions</span>
        </div>

        <div class="cp-table-scroll" role="region" aria-label="Матрица ролей и прав" tabindex="0">
          <table class="cp-table rbac-matrix">
            <thead>
              <tr>
                <th scope="col">Permission</th>
                <th v-for="role in roles" :key="role.code" scope="col">{{ roleLabel(role.code) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="permission in permissions" :key="permission">
                <td>
                  <strong>{{ permissionLabel(permission) }}</strong>
                  <code class="cp-code rbac-permission-code">{{ permission }}</code>
                </td>
                <td v-for="role in roles" :key="`${permission}:${role.code}`" class="rbac-matrix__cell">
                  <span
                    class="rbac-check"
                    :class="{ 'rbac-check--yes': hasRolePermission(role.code, permission) }"
                    :aria-label="hasRolePermission(role.code, permission) ? 'Разрешено' : 'Запрещено'"
                  >
                    {{ hasRolePermission(role.code, permission) ? '✓' : '—' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-if="!canManageRoles" class="cp-state">
        У вас есть <code>roles:read</code>, поэтому матрица и назначения доступны для просмотра. Изменение ролей требует <code>roles:write</code>.
      </div>

      <div v-if="actionError" class="cp-state cp-state--error" role="alert">{{ actionError }}</div>

      <section class="cp-table-wrap">
        <div class="cp-table__toolbar">
          <div>
            <strong>Назначения ролей</strong>
            <div class="cp-muted">Роль определяет набор permissions, а аудит показывает фактические действия пользователя.</div>
          </div>
          <span class="cp-table__count">{{ users.length }} пользователей</span>
        </div>

        <div class="cp-table-scroll" role="region" aria-label="Назначения ролей пользователям" tabindex="0">
          <table class="cp-table">
            <thead>
              <tr>
                <th scope="col">Пользователь</th>
                <th scope="col">Текущие роли</th>
                <th scope="col">Эффективные права</th>
                <th scope="col">Назначить роль</th>
                <th scope="col">Действия</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="user in users" :key="user.id">
                <tr>
                  <td>
                    <div class="cp-person">
                      <div class="cp-avatar" aria-hidden="true">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
                      <div>
                        <div class="cp-person__name">{{ user.full_name || 'Не указано' }}</div>
                        <div class="cp-muted">{{ user.email }}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="cp-chip-row">
                      <span v-for="item in user.roles" :key="item.role" class="cp-chip cp-chip--accent cp-role-chip">
                        {{ roleLabel(item.role) }}
                        <button
                          v-if="canManageRoles && item.role !== 'user'"
                          class="cp-role-chip__remove"
                          type="button"
                          :title="`Удалить роль ${roleLabel(item.role)}`"
                          :aria-label="`Удалить роль ${roleLabel(item.role)} у ${user.full_name || user.email}`"
                          :disabled="isActing"
                          @click="askRemoveRole(user, item.role)"
                        >×</button>
                      </span>
                      <span v-if="!user.roles?.length" class="cp-muted">Роли не назначены</span>
                    </div>
                  </td>
                  <td>
                    <button class="rbac-permissions-button" type="button" @click="toggleUserPermissions(user.id)">
                      {{ effectivePermissions(user).length }} прав
                      <span aria-hidden="true">{{ expandedUserId === user.id ? '↑' : '↓' }}</span>
                    </button>
                  </td>
                  <td>
                    <div class="cp-role-assign">
                      <select
                        v-model="selectedRoles[user.id]"
                        class="cp-form-select cp-role-select"
                        :aria-label="`Назначить роль пользователю ${user.full_name || user.email}`"
                        :disabled="!canManageRoles || isActing || assignableRoles(user).length === 0"
                      >
                        <option value="" disabled>{{ assignableRoles(user).length ? 'Выберите роль' : 'Все роли назначены' }}</option>
                        <option v-for="role in assignableRoles(user)" :key="role" :value="role">{{ roleLabel(role) }}</option>
                      </select>
                      <BaseButton
                        variant="primary"
                        size="small"
                        text="Назначить"
                        loading-text="Назначаем…"
                        :disabled="!canManageRoles || isActing || !selectedRoles[user.id]"
                        :loading="actionKey === `assign:${user.id}`"
                        @click="assignRole(user)"
                      />
                    </div>
                  </td>
                  <td>
                    <RouterLink
                      class="rbac-audit-link"
                      :to="{ name: 'control-panel.audit', query: { actor_id: user.id } }"
                    >Аудит действий →</RouterLink>
                  </td>
                </tr>
                <tr v-if="expandedUserId === user.id" class="rbac-permissions-row">
                  <td colspan="5">
                    <Transition name="cp-expand" appear>
                      <div class="rbac-effective-list">
                        <span
                          v-for="permission in effectivePermissions(user)"
                          :key="permission"
                          class="cp-chip"
                        >{{ permissionLabel(permission) }}</span>
                        <span v-if="effectivePermissions(user).length === 0" class="cp-muted">Нет административных permissions.</span>
                      </div>
                    </Transition>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <Modal
      v-if="removeConfirm.isOpen"
      :is-open="true"
      aria-label="Подтверждение отзыва роли"
      :close-on-overlay-click="!isActing"
      :close-on-escape="!isActing"
      @close="closeRemoveConfirm"
    >
      <template #header><h3 class="cp-modal-title">Отозвать роль</h3></template>
      <template #body>
        <p class="cp-modal-copy">
          Отозвать роль «{{ roleLabel(removeConfirm.role) }}» у пользователя
          «{{ removeConfirm.user?.full_name || removeConfirm.user?.email }}»? Backend пересчитает доступ немедленно.
        </p>
      </template>
      <template #footer>
        <div class="cp-modal-footer">
          <BaseButton variant="outline" text="Отмена" :disabled="isActing" @click="closeRemoveConfirm" />
          <BaseButton variant="danger" text="Отозвать роль" loading-text="Отзываем…" :loading="isActing" @click="removeRoleConfirmed" />
        </div>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.rbac-contract {
  margin-bottom: 2px;
}

.rbac-role-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.rbac-role-card {
  min-height: 170px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rbac-role-card__head,
.rbac-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.rbac-mini-permissions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rbac-mini-permission {
  padding: 4px 7px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--light-bg);
  color: var(--text-muted);
  font-size: 11px;
}

.rbac-matrix-card {
  padding: 20px;
}

.rbac-section-head {
  margin-bottom: 16px;
}

.rbac-section-title {
  margin-top: 2px;
  font-size: 20px;
}

.rbac-matrix th:not(:first-child),
.rbac-matrix__cell {
  min-width: 118px;
  text-align: center;
}

.rbac-matrix td:first-child {
  min-width: 260px;
}

.rbac-permission-code {
  display: block;
  width: fit-content;
  margin-top: 4px;
}

.rbac-check {
  width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border-radius: 8px;
  color: var(--text-subtle);
  background: var(--light-bg);
  font-weight: 800;
}

.rbac-check--yes {
  color: var(--success-color);
  background: color-mix(in srgb, var(--success-color) 10%, var(--card-bg));
}

.cp-role-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.cp-role-chip__remove {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 17px;
  line-height: 1;
  padding: 0;
  opacity: .75;
}

.cp-role-chip__remove:hover,
.cp-role-chip__remove:focus-visible {
  opacity: 1;
}

.cp-role-chip__remove:disabled {
  cursor: not-allowed;
  opacity: .4;
}

.cp-role-assign {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 310px;
}

.cp-role-select {
  flex: 1;
}

.rbac-permissions-button,
.rbac-audit-link {
  border: 0;
  background: transparent;
  color: var(--secondary-color);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
  white-space: nowrap;
}

.rbac-permissions-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 0;
}

.rbac-audit-link:hover,
.rbac-permissions-button:hover {
  text-decoration: underline;
}

.rbac-permissions-row td {
  padding-top: 0;
  background: var(--light-bg);
}

.rbac-effective-list {
  min-height: 48px;
  padding: 12px 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

@media (max-width: 1000px) {
  .rbac-role-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .rbac-role-summary {
    grid-template-columns: 1fr;
  }

  .cp-role-assign {
    min-width: 240px;
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
