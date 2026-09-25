<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import CP_Users from '@/API/ControlPanel/CP_Users'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import ManageRolesModal from '@/components/UserModals/manage_roles.vue'

const authStore = useAuthStore()
const users = ref([])
const roles = ref([])
const permissions = ref([])
const canManageRoles = ref(false)
const manageUser = ref(null)
const isLoading = ref(false)
const loadError = ref('')

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь',
}

const ROLE_DESCRIPTIONS = {
	super_admin: 'Полный системный доступ. Управление ролями и критическими настройками.',
	admin: 'Управление пользователями и тарифами, просмотр платежей, аудита и рассылок.',
	manager: 'Просмотр операционных разделов без изменения критических данных.',
	support: 'Работа с пользовательскими карточками и аудитом без административных write-операций.',
	analyst: 'Операционная сводка без доступа к персональным карточкам и критическим настройкам.',
	user: 'Базовый клиентский доступ без панели управления.',
}

const PERMISSION_LABELS = {
	'control_panel:access': 'Доступ к панели управления',
	'system:manage': 'Системные настройки',
	'users:read': 'Пользователи · просмотр',
	'users:write': 'Пользователи · изменение',
	'users:delete': 'Пользователи · удаление',
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

const currentUserId = computed(() => String(authStore.user?.id || ''))
const roleLabel = (role) => ROLE_LABELS[role] || role
const permissionLabel = (permission) => PERMISSION_LABELS[permission] || permission
const roleByCode = (code) => roles.value.find(role => role.code === code)
const hasRolePermission = (code, permission) =>
	(roleByCode(code)?.permissions || []).includes(permission)

function effectivePermissions(user) {
	if (Array.isArray(user.permissions)) return user.permissions
	const result = new Set()
	for (const item of user.roles || []) {
		for (const permission of roleByCode(item.role)?.permissions || []) {
			result.add(permission)
		}
	}
	return [...result].sort()
}

function isSelf(user) {
	return String(user?.id || '') === currentUserId.value
}

async function loadData() {
	isLoading.value = true
	loadError.value = ''
	try {
		const [usersResponse, rolesResponse] = await Promise.all([
			CP_Users.getUserList({ limit: 200, sort_by: 'user', sort_order: 'asc' }),
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
		permissions.value = Array.isArray(rolesResponse.data.permissions)
			? rolesResponse.data.permissions
			: []
		canManageRoles.value = Boolean(rolesResponse.data.can_manage)
	} catch (error) {
		console.error('Ошибка загрузки управления ролями:', error)
		loadError.value =
			error.response?.data?.error?.message ||
			'Не удалось загрузить пользователей и роли.'
	} finally {
		isLoading.value = false
	}
}

function openRoleManager(user) {
	manageUser.value = user
}

function closeRoleManager() {
	manageUser.value = null
}

async function handleRolesChanged() {
	manageUser.value = null
	await loadData()
}

onMounted(loadData)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Доступ</p>
				<h2 class="cp-detail-title">Роли пользователей</h2>
				<p class="cp-subtitle">Здесь показаны только роли, назначенные сейчас. Изменение выполняется отдельным подтверждаемым действием.</p>
			</div>
		</header>

		<div class="cp-info-callout role-model-notice">
			<strong>Роли суммируются, а не заменяют друг друга.</strong>
			<span>Если у пользователя одновременно «Пользователь» и «Администратор», обе роли назначены сейчас. Ни один select на этой странице больше не показывает будущую роль как будто она уже активна.</span>
		</div>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем пользователей и роли…</div>
		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadData" />
			</div>
		</div>

		<template v-else>
			<section class="cp-table-wrap role-users">
				<div class="cp-table__toolbar">
					<div>
						<strong>Текущие назначения</strong>
						<div class="cp-muted">Таблица показывает фактическое состояние из БД.</div>
					</div>
					<span class="cp-table__count">{{ users.length }} пользователей</span>
				</div>

				<div class="cp-table-scroll" role="region" aria-label="Текущие роли пользователей" tabindex="0">
					<table class="cp-table role-users-table">
						<thead>
							<tr>
								<th scope="col">Пользователь</th>
								<th scope="col">Текущие роли</th>
								<th scope="col">Эффективный доступ</th>
								<th scope="col">Действия</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="user in users" :key="user.id">
								<td>
									<div class="cp-person">
										<div class="cp-avatar" aria-hidden="true">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
										<div>
											<div class="cp-person__name">
												{{ user.full_name || 'Не указано' }}
												<span v-if="isSelf(user)" class="self-mark">Это вы</span>
											</div>
											<div class="cp-muted">{{ user.email }}</div>
										</div>
									</div>
								</td>
								<td>
									<div class="cp-chip-row">
										<span v-for="item in user.roles" :key="item.role" class="cp-chip cp-chip--accent">{{ roleLabel(item.role) }}</span>
										<span v-if="!user.roles?.length" class="cp-muted">Роли не назначены</span>
									</div>
								</td>
								<td>
									<div class="access-summary">
										<strong>{{ effectivePermissions(user).length }} прав</strong>
										<span>{{ effectivePermissions(user).includes('control_panel:access') ? 'Панель управления доступна' : 'Нет административного доступа' }}</span>
									</div>
								</td>
								<td>
									<div class="role-row-actions">
										<BaseButton
											variant="outline"
											size="small"
											:text="canManageRoles ? 'Изменить роли' : 'Посмотреть роли'"
											@click="openRoleManager(user)"
										/>
										<RouterLink class="rbac-audit-link" :to="{ name: 'control-panel.audit', query: { actor_id: user.id } }">Аудит</RouterLink>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<details class="cp-card role-reference">
				<summary>
					<div>
						<strong>Справочник ролей и permissions</strong>
						<span>Техническая матрица для проверки RBAC. Для обычной смены роли открывать её не нужно.</span>
					</div>
					<span class="role-reference__hint">Показать</span>
				</summary>

				<div class="role-reference__body">
					<section class="rbac-role-summary">
						<article v-for="role in roles" :key="role.code" class="role-reference-card">
							<div class="role-reference-card__head">
								<span class="cp-chip cp-chip--accent">{{ roleLabel(role.code) }}</span>
								<span class="cp-muted">{{ role.permissions.length }} прав</span>
							</div>
							<p>{{ ROLE_DESCRIPTIONS[role.code] || role.code }}</p>
						</article>
					</section>

					<div class="rbac-section-head">
						<div>
							<p class="cp-eyebrow">Матрица доступа</p>
							<h3 class="cp-section-title">Какие permissions даёт каждая роль</h3>
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
										<span class="rbac-check" :class="{ 'rbac-check--yes': hasRolePermission(role.code, permission) }">{{ hasRolePermission(role.code, permission) ? '✓' : '—' }}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</details>
		</template>

		<ManageRolesModal
			v-if="manageUser"
			:is-open="true"
			:user="manageUser"
			:current-user-id="currentUserId"
			@close="closeRoleManager"
			@changed="handleRolesChanged"
		/>
	</section>
</template>

<style scoped>
.role-users { overflow: hidden; }
.role-users-table { min-width: 820px; }
.role-users-table th:nth-child(1) { width: 30%; }
.role-users-table th:nth-child(2) { width: 28%; }
.role-users-table th:nth-child(3) { width: 24%; }
.role-users-table th:nth-child(4) { width: 18%; }

.self-mark {
	margin-left: 6px;
	padding: 2px 6px;
	border-radius: 999px;
	background: color-mix(in srgb, var(--secondary-color) 10%, var(--card-bg));
	color: var(--secondary-color);
	font-size: 9px;
	font-weight: 800;
}

.access-summary { display: grid; gap: 3px; }
.access-summary strong { font-size: 12px; }
.access-summary span { color: var(--text-muted); font-size: 10px; }
.role-row-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rbac-audit-link { color: var(--secondary-color); font-size: 11px; font-weight: 700; text-decoration: none; }
.rbac-audit-link:hover { text-decoration: underline; }

.role-reference { padding: 0; overflow: hidden; }
.role-reference > summary {
	padding: 16px 18px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	list-style: none;
	cursor: pointer;
}
.role-reference > summary::-webkit-details-marker { display: none; }
.role-reference > summary > div { display: grid; gap: 3px; }
.role-reference > summary strong { font-size: 14px; }
.role-reference > summary span { color: var(--text-muted); font-size: 11px; }
.role-reference__hint { color: var(--secondary-color) !important; font-weight: 750; }
.role-reference[open] .role-reference__hint { font-size: 0; }
.role-reference[open] .role-reference__hint::after { content: 'Скрыть'; font-size: 11px; }

.role-reference__body {
	padding: 18px;
	display: grid;
	gap: 18px;
	border-top: 1px solid var(--border-color);
}
.rbac-role-summary {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}
.role-reference-card {
	padding: 12px;
	display: grid;
	gap: 8px;
	border: 1px solid var(--border-color);
	border-radius: 10px;
	background: var(--card-bg);
}
.role-reference-card__head,
.rbac-section-head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
}
.role-reference-card p { margin: 0; color: var(--text-muted); font-size: 11px; line-height: 1.45; }
.rbac-section-head { margin-top: 4px; }
.rbac-matrix th:not(:first-child),
.rbac-matrix__cell { min-width: 108px; text-align: center; }
.rbac-matrix td:first-child { min-width: 250px; }
.rbac-permission-code { display: block; width: fit-content; margin-top: 4px; }
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

@media (max-width: 900px) {
	.rbac-role-summary { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 640px) {
	.rbac-role-summary { grid-template-columns: 1fr; }
}
</style>
