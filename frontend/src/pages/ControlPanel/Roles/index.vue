<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import CP_Users from '@/API/ControlPanel/CP_Users'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const authStore = useAuthStore()
const users = ref([])
const roles = ref([])
const selectedRoles = ref({})
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionKey = ref('')

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
}

const ROLE_DESCRIPTIONS = {
	super_admin: 'Полный доступ, включая назначение и отзыв системных ролей.',
	admin: 'Управление пользователями и тарифами без изменения ролей суперадминов.',
	manager: 'Операционная роль без доступа к панели управления.',
	support: 'Поддержка пользователей без административной конфигурации.',
	analyst: 'Аналитическая роль без административной конфигурации.',
	user: 'Базовая пользовательская роль.'
}

const isSuperAdmin = computed(() => Array.isArray(authStore.user?.roles) && authStore.user.roles.includes('super_admin'))
const roleLabel = (role) => ROLE_LABELS[role] || role
const userRoleCodes = (user) => (user.roles || []).map((role) => role.role)
const assignableRoles = (user) => roles.value.filter((role) => !userRoleCodes(user).includes(role))

async function loadData() {
	isLoading.value = true
	loadError.value = ''
	actionError.value = ''
	try {
		const [usersResponse, rolesResponse] = await Promise.all([
			CP_Users.getUserList(),
			CP_Roles.getRolesList()
		])
		if (usersResponse.data?.status !== 'success' || !Array.isArray(usersResponse.data?.user_list)) {
			throw new Error('Некорректный ответ API пользователей')
		}
		if (rolesResponse.data?.status !== 'success' || !Array.isArray(rolesResponse.data?.roles)) {
			throw new Error('Некорректный ответ API ролей')
		}
		users.value = usersResponse.data.user_list
		roles.value = rolesResponse.data.roles
		for (const user of users.value) {
			selectedRoles.value[user.id] = assignableRoles(user)[0] || ''
		}
	} catch (error) {
		console.error('Ошибка загрузки управления ролями:', error)
		loadError.value = 'Не удалось загрузить пользователей и роли.'
	} finally {
		isLoading.value = false
	}
}

async function assignRole(user) {
	const role = selectedRoles.value[user.id]
	if (!role || !isSuperAdmin.value) return
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

async function removeRole(user, role) {
	if (!isSuperAdmin.value || role === 'user') return
	actionKey.value = `remove:${user.id}:${role}`
	actionError.value = ''
	try {
		const response = await CP_Roles.deleteRoleFromUser(user.id, role)
		if (response.data?.status !== 'success') {
			throw new Error(response.data?.error?.message || response.data?.message || 'Не удалось удалить роль')
		}
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
				<p class="cp-subtitle">Системные роли пользователей и управление административным доступом.</p>
			</div>
		</header>

		<div class="cp-overview-grid cp-role-cards">
			<article v-for="role in roles" :key="role" class="cp-card cp-role-card">
				<div class="cp-chip cp-chip--accent">{{ roleLabel(role) }}</div>
				<p class="cp-card-note">{{ ROLE_DESCRIPTIONS[role] || role }}</p>
			</article>
		</div>

		<div v-if="!isSuperAdmin" class="cp-state">
			Назначение и отзыв ролей доступны только суперадминистратору. Текущие назначения доступны для просмотра.
		</div>

		<div v-if="actionError" class="cp-state cp-state--error" role="alert">{{ actionError }}</div>
		<div v-if="isLoading" class="cp-state" role="status">Загружаем роли…</div>
		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadData" />
			</div>
		</div>

		<div v-else class="cp-table-wrap">
			<div class="cp-table__toolbar">
				<strong>Назначения ролей</strong>
				<span class="cp-table__count">{{ users.length }} пользователей</span>
			</div>
			<div class="cp-table-scroll">
				<table class="cp-table">
					<thead>
						<tr>
							<th>Пользователь</th>
							<th>Текущие роли</th>
							<th>Назначить роль</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="user in users" :key="user.id">
							<td>
								<div class="cp-person">
									<div class="cp-avatar">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
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
											v-if="isSuperAdmin && item.role !== 'user'"
											class="cp-role-chip__remove"
											type="button"
											:title="`Удалить роль ${roleLabel(item.role)}`"
											:disabled="actionKey === `remove:${user.id}:${item.role}`"
											@click="removeRole(user, item.role)"
										>×</button>
									</span>
									<span v-if="!user.roles?.length" class="cp-muted">Роли не назначены</span>
								</div>
							</td>
							<td>
								<div class="cp-role-assign">
									<select v-model="selectedRoles[user.id]" class="cp-role-select" :disabled="!isSuperAdmin || assignableRoles(user).length === 0">
										<option value="" disabled>{{ assignableRoles(user).length ? 'Выберите роль' : 'Все роли назначены' }}</option>
										<option v-for="role in assignableRoles(user)" :key="role" :value="role">{{ roleLabel(role) }}</option>
									</select>
									<BaseButton
										variant="primary"
										size="small"
										text="Назначить"
										:disabled="!isSuperAdmin || !selectedRoles[user.id]"
										:loading="actionKey === `assign:${user.id}`"
										@click="assignRole(user)"
									/>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</section>
</template>

<style scoped>
.cp-role-cards { margin-bottom: 18px; }
.cp-role-card { min-height: 118px; display: flex; flex-direction: column; gap: 12px; }
.cp-role-chip { display: inline-flex; align-items: center; gap: 7px; }
.cp-role-chip__remove { border: 0; background: transparent; color: inherit; cursor: pointer; font-size: 17px; line-height: 1; padding: 0; opacity: .75; }
.cp-role-chip__remove:hover { opacity: 1; }
.cp-role-chip__remove:disabled { cursor: wait; opacity: .4; }
.cp-role-assign { display: flex; align-items: center; gap: 8px; min-width: 310px; }
.cp-role-select { min-height: 38px; flex: 1; border: 1px solid var(--cp-border, #2b3a4c); border-radius: 8px; background: var(--cp-surface, #151e2b); color: inherit; padding: 0 10px; }
.cp-role-select:disabled { opacity: .55; }
@media (max-width: 760px) { .cp-role-assign { min-width: 240px; flex-direction: column; align-items: stretch; } }
</style>
