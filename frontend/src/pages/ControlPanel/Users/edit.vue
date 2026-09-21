<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import DateTransform from '@/utils/date_transform'
import EditUserModal from '@/components/UserModals/edit_user.vue'
import AssignRoleModal from '@/components/UserModals/assign_role.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const targetUser = ref(null)
const isLoading = ref(false)
const loadError = ref('')
const roleActionLoading = ref(false)
const accountActionLoading = ref('')
const showEditModal = ref(false)
const showAssignRoleModal = ref(false)
const roleConfirm = ref({ isOpen: false, role: '' })

const ENTITY_LABELS = {
	individual: 'Физическое лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юридическое лицо'
}

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
}

const actorRoles = computed(() => authStore.user?.roles || [])
const actorIsSuperAdmin = computed(() => actorRoles.value.includes('super_admin'))
const canManageUsers = computed(() => actorIsSuperAdmin.value || actorRoles.value.includes('admin'))
const canManageRoles = computed(() => actorIsSuperAdmin.value)
const targetIsSuperAdmin = computed(() => targetUser.value?.roles?.some((item) => item.role === 'super_admin'))
const isSelf = computed(() => String(authStore.user?.id || '') === String(targetUser.value?.id || ''))
const canManageTarget = computed(() =>
	canManageUsers.value && (!targetIsSuperAdmin.value || actorIsSuperAdmin.value)
)
const emailVerified = computed(() => Boolean(targetUser.value?.email_verified_at))

onMounted(loadUser)

async function loadUser() {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Users.getUser(route.params.id)
		if (data?.status === 'success') {
			targetUser.value = data.target_user
		} else {
			targetUser.value = null
			loadError.value = 'Пользователь не найден.'
		}
	} catch (error) {
		console.error('Ошибка загрузки пользователя:', error)
		targetUser.value = null
		loadError.value = 'Не удалось загрузить данные пользователя.'
	} finally {
		isLoading.value = false
	}
}

function askRemoveRole(roleCode) {
	if (roleActionLoading.value || !canManageRoles.value) return
	roleConfirm.value = { isOpen: true, role: roleCode }
}

function closeRoleConfirm() {
	if (roleActionLoading.value) return
	roleConfirm.value = { isOpen: false, role: '' }
}

async function removeRoleConfirmed() {
	if (roleActionLoading.value || !targetUser.value || !roleConfirm.value.role || !canManageRoles.value) return
	roleActionLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Roles.deleteRoleFromUser(targetUser.value.id, roleConfirm.value.role)
		if (response.data?.status !== 'success') throw new Error(response.data?.message || 'Не удалось удалить роль')
		roleConfirm.value = { isOpen: false, role: '' }
		await loadUser()
	} catch (error) {
		console.error('Ошибка удаления роли:', error)
		loadError.value = error.response?.data?.error?.message || error.message || 'Не удалось удалить роль. Повторите действие.'
	} finally {
		roleActionLoading.value = false
	}
}

async function runAccountAction(kind) {
	if (!targetUser.value || !canManageTarget.value || accountActionLoading.value) return

	const prompts = {
		verify: 'Подтвердить email пользователя вручную? Действие будет записано в журнал lifecycle.',
		reactivate: 'Активировать аккаунт пользователя?',
		deactivate: 'Деактивировать аккаунт? Текущие сессии будут отозваны.',
		revoke: 'Отозвать все активные сессии пользователя?'
	}
	if (!window.confirm(prompts[kind])) return

	accountActionLoading.value = kind
	loadError.value = ''
	try {
		let response
		if (kind === 'verify') response = await CP_Users.verifyEmail(targetUser.value.id, 'manual_control_panel_verification')
		if (kind === 'reactivate') response = await CP_Users.reactivateUser(targetUser.value.id, 'manual_control_panel_reactivation')
		if (kind === 'deactivate') response = await CP_Users.deactivateUser(targetUser.value.id)
		if (kind === 'revoke') response = await CP_Users.revokeSessions(targetUser.value.id, 'manual_control_panel_revocation')
		if (response?.data?.status !== 'success') throw new Error(response?.data?.error?.message || 'Операция не выполнена')
		await loadUser()
	} catch (error) {
		console.error('Ошибка операции с аккаунтом:', error)
		loadError.value = error.response?.data?.error?.message || error.message || 'Не удалось выполнить операцию.'
	} finally {
		accountActionLoading.value = ''
	}
}
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Пользователи · профиль</p>
				<h2 class="cp-detail-title">Карточка пользователя</h2>
				<p class="cp-subtitle">Профиль, идентификация, статус аккаунта, безопасность и роли.</p>
			</div>
			<BaseButton variant="outline" size="small" text="← К списку" @click="router.push({ name: 'control-panel.users' })" />
		</header>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем данные пользователя…</div>

		<div v-else-if="loadError && !targetUser" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadUser" />
			</div>
		</div>

		<template v-else-if="targetUser">
			<article class="cp-card cp-detail-card">
				<div class="cp-detail-header">
					<div>
						<h3 class="cp-detail-title">{{ targetUser.full_name || 'Без имени' }}</h3>
						<p class="cp-detail-meta">{{ targetUser.email }}<span v-if="targetUser.phone"> · {{ targetUser.phone }}</span></p>
					</div>
					<div class="cp-chip-row">
						<span class="cp-chip" :class="targetUser.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
							{{ targetUser.is_active ? 'Активен' : 'Неактивен' }}
						</span>
						<span class="cp-chip" :class="emailVerified ? 'cp-chip--active' : 'cp-chip--warning'">
							{{ emailVerified ? 'Email подтверждён' : 'Email не подтверждён' }}
						</span>
						<span v-if="targetUser.is_staff" class="cp-chip cp-chip--accent">Сотрудник</span>
					</div>
				</div>

				<div v-if="loadError" class="cp-state cp-state--error cp-state--compact" role="alert">
					{{ loadError }}
				</div>

				<div class="cp-info-grid">
					<div class="cp-info-item"><span class="cp-info-label">ID</span><code class="cp-info-value cp-code">{{ targetUser.id }}</code></div>
					<div class="cp-info-item"><span class="cp-info-label">Тип аккаунта</span><span class="cp-info-value">{{ ENTITY_LABELS[targetUser.entity_type] || targetUser.entity_type || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Создан</span><span class="cp-info-value">{{ DateTransform.formatDate(targetUser.created_at) }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Email подтверждён</span><span class="cp-info-value">{{ targetUser.email_verified_at ? DateTransform.formatDate(targetUser.email_verified_at) : 'Нет' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Часовой пояс</span><span class="cp-info-value">{{ targetUser.timezone || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Налоговая ставка</span><span class="cp-info-value">{{ Number(targetUser.tax_rate ?? 0) * 100 }}%</span></div>
					<div class="cp-info-item"><span class="cp-info-label">ИНН</span><span class="cp-info-value">{{ targetUser.inn || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">КПП</span><span class="cp-info-value">{{ targetUser.kpp || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Юр. адрес</span><span class="cp-info-value">{{ targetUser.legal_address || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">ID сотрудника</span><span class="cp-info-value">{{ targetUser.staff_id || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Отдел</span><span class="cp-info-value">{{ targetUser.department || '—' }}</span></div>
					<div class="cp-info-item"><span class="cp-info-label">Должность</span><span class="cp-info-value">{{ targetUser.position || '—' }}</span></div>
				</div>

				<section v-if="canManageTarget" class="cp-section">
					<div class="cp-section-header">
						<div>
							<h3 class="cp-section-title">Управление аккаунтом</h3>
							<p class="cp-muted">Операции доступа выполняются через lifecycle-контур и фиксируются на backend.</p>
						</div>
					</div>
					<div class="account-actions">
						<BaseButton
							v-if="!emailVerified"
							variant="success"
							text="Подтвердить email"
							loading-text="Подтверждаем…"
							:loading="accountActionLoading === 'verify'"
							:disabled="Boolean(accountActionLoading)"
							@click="runAccountAction('verify')"
						/>
						<BaseButton
							v-if="!targetUser.is_active"
							variant="success"
							text="Активировать аккаунт"
							loading-text="Активируем…"
							:loading="accountActionLoading === 'reactivate'"
							:disabled="Boolean(accountActionLoading)"
							@click="runAccountAction('reactivate')"
						/>
						<BaseButton
							v-if="targetUser.is_active && !isSelf"
							variant="danger"
							text="Деактивировать"
							loading-text="Деактивируем…"
							:loading="accountActionLoading === 'deactivate'"
							:disabled="Boolean(accountActionLoading)"
							@click="runAccountAction('deactivate')"
						/>
						<BaseButton
							v-if="!isSelf"
							variant="outline"
							text="Отозвать сессии"
							loading-text="Отзываем…"
							:loading="accountActionLoading === 'revoke'"
							:disabled="Boolean(accountActionLoading)"
							@click="runAccountAction('revoke')"
						/>
						<BaseButton
							variant="primary"
							text="Редактировать профиль"
							:disabled="Boolean(accountActionLoading)"
							@click="showEditModal = true"
						/>
					</div>
				</section>

				<section class="cp-section">
					<div class="cp-section-header">
						<div>
							<h3 class="cp-section-title">Роли и доступ</h3>
							<p class="cp-muted">
								{{ canManageRoles ? 'Системные роли управляются только суперадминистратором.' : 'Доступно только чтение назначенных ролей.' }}
							</p>
						</div>
						<BaseButton
							v-if="canManageRoles"
							variant="success"
							size="small"
							text="Назначить роль"
							:disabled="roleActionLoading"
							@click="showAssignRoleModal = true"
						/>
					</div>

					<div v-if="targetUser.roles?.length" class="cp-list">
						<div v-for="roleItem in targetUser.roles" :key="roleItem.role" class="cp-list-row">
							<div class="cp-list-row__main">
								<div class="cp-chip-row"><span class="cp-chip cp-chip--accent">{{ ROLE_LABELS[roleItem.role] || roleItem.role }}</span></div>
								<p class="cp-list-row__meta">
									Назначена: {{ DateTransform.formatDate(roleItem.assigned_at) }}
									<span v-if="roleItem.assigned_by"> · {{ roleItem.assigned_by }}</span>
								</p>
							</div>
							<button
								v-if="canManageRoles && roleItem.role !== 'user'"
								class="cp-icon-button cp-icon-button--danger"
								title="Удалить роль"
								:aria-label="`Удалить роль ${roleItem.role}`"
								:disabled="roleActionLoading"
								@click="askRemoveRole(roleItem.role)"
							>×</button>
						</div>
					</div>
					<div v-else class="cp-state">Роли не назначены.</div>
				</section>
			</article>

			<EditUserModal v-if="showEditModal" :is-open="true" :current-user="targetUser" @close="showEditModal = false" @updated="loadUser" />
			<AssignRoleModal :is-open="showAssignRoleModal" :user-id="targetUser?.id" @close="showAssignRoleModal = false" @assigned="loadUser" />
		</template>

		<Modal
			v-if="roleConfirm.isOpen"
			:is-open="true"
			aria-label="Подтверждение удаления роли"
			:close-on-overlay-click="!roleActionLoading"
			:close-on-escape="!roleActionLoading"
			@close="closeRoleConfirm"
		>
			<template #header><h3 class="cp-modal-title">Удалить роль</h3></template>
			<template #body><p class="cp-modal-copy">Удалить роль «{{ ROLE_LABELS[roleConfirm.role] || roleConfirm.role }}» у пользователя? Доступ изменится сразу после сохранения.</p></template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton variant="outline" text="Отмена" :disabled="roleActionLoading" @click="closeRoleConfirm" />
					<BaseButton variant="danger" text="Удалить роль" loading-text="Удаляем…" :loading="roleActionLoading" @click="removeRoleConfirmed" />
				</div>
			</template>
		</Modal>
	</section>
</template>

<style scoped>
.account-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 9px;
}

.cp-state--compact {
	min-height: auto;
	margin-bottom: 14px;
}
</style>
