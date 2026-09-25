<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users'
import DateTransform from '@/utils/date_transform'
import EditUserModal from '@/components/UserModals/edit_user.vue'
import ManageRolesModal from '@/components/UserModals/manage_roles.vue'
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
const accountActionLoading = ref('')
const showEditModal = ref(false)
const showManageRolesModal = ref(false)
const deleteConfirm = ref({ isOpen: false, email: '', reason: '', error: '' })

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
const canPermanentlyDelete = computed(() =>
	canManageTarget.value &&
	!isSelf.value &&
	targetUser.value &&
	targetUser.value.is_active === false
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

function openPermanentDelete() {
	if (!canPermanentlyDelete.value || accountActionLoading.value) return
	deleteConfirm.value = {
		isOpen: true,
		email: '',
		reason: '',
		error: '',
	}
}

function closePermanentDelete() {
	if (accountActionLoading.value === 'purge') return
	deleteConfirm.value = { isOpen: false, email: '', reason: '', error: '' }
}

async function permanentlyDeleteConfirmed() {
	if (!targetUser.value || !canPermanentlyDelete.value || accountActionLoading.value) return

	const expectedEmail = String(targetUser.value.email || '').trim().toLowerCase()
	const confirmation = String(deleteConfirm.value.email || '').trim().toLowerCase()
	if (!confirmation || confirmation !== expectedEmail) {
		deleteConfirm.value.error = 'Введите email пользователя точно так, как он указан в карточке.'
		return
	}

	accountActionLoading.value = 'purge'
	deleteConfirm.value.error = ''
	try {
		const response = await CP_Users.permanentlyDeleteUser(
			targetUser.value.id,
			confirmation,
			String(deleteConfirm.value.reason || '').trim(),
		)
		if (response.data?.status !== 'success' || response.data?.deleted !== true) {
			throw new Error(response.data?.error?.message || 'Пользователь не удалён')
		}
		deleteConfirm.value = { isOpen: false, email: '', reason: '', error: '' }
		await router.push({ name: 'control-panel.users' })
	} catch (error) {
		console.error('Ошибка необратимого удаления пользователя:', error)
		deleteConfirm.value.error =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось удалить пользователя. Повторите действие.'
	} finally {
		accountActionLoading.value = ''
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
							v-if="canPermanentlyDelete"
							variant="danger"
							text="Удалить навсегда"
							loading-text="Удаляем…"
							:loading="accountActionLoading === 'purge'"
							:disabled="Boolean(accountActionLoading)"
							@click="openPermanentDelete"
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
							<p class="cp-muted">Показаны только роли, назначенные сейчас. Добавление роли не заменяет существующие.</p>
						</div>
						<BaseButton
							v-if="canManageRoles"
							variant="outline"
							size="small"
							text="Изменить роли"
							@click="showManageRolesModal = true"
						/>
					</div>

					<div v-if="targetUser.roles?.length" class="cp-chip-row">
						<span v-for="roleItem in targetUser.roles" :key="roleItem.role" class="cp-chip cp-chip--accent">
							{{ ROLE_LABELS[roleItem.role] || roleItem.role }}
						</span>
					</div>
					<div v-else class="cp-state cp-state--compact">Роли не назначены.</div>

					<p v-if="isSelf && targetIsSuperAdmin" class="cp-muted">
						Собственную роль суперадминистратора снять нельзя. Это дополнительно защищено backend.
					</p>
				</section>
			</article>

			<EditUserModal v-if="showEditModal" :is-open="true" :current-user="targetUser" @close="showEditModal = false" @updated="loadUser" />
			<ManageRolesModal
				v-if="showManageRolesModal"
				:is-open="true"
				:user="targetUser"
				:current-user-id="String(authStore.user?.id || '')"
				@close="showManageRolesModal = false"
				@changed="loadUser"
			/>
		</template>

		<Modal
			v-if="deleteConfirm.isOpen"
			:is-open="true"
			aria-label="Подтверждение необратимого удаления пользователя"
			:close-on-overlay-click="accountActionLoading !== 'purge'"
			:close-on-escape="accountActionLoading !== 'purge'"
			@close="closePermanentDelete"
		>
			<template #header>
				<h3 class="cp-modal-title">Удалить пользователя навсегда</h3>
			</template>
			<template #body>
				<div class="cp-modal-stack">
					<p class="cp-modal-copy">
						Аккаунт и связанные пользовательские данные будут удалены необратимо.
						Для подтверждения введите email <strong>{{ targetUser?.email }}</strong>.
					</p>
					<label class="cp-field-label">
						<span>Email для подтверждения</span>
						<input
							v-model="deleteConfirm.email"
							type="email"
							autocomplete="off"
							:placeholder="targetUser?.email || ''"
							:disabled="accountActionLoading === 'purge'"
						/>
					</label>
					<label class="cp-field-label">
						<span>Причина удаления <small class="cp-muted">необязательно</small></span>
						<textarea
							v-model="deleteConfirm.reason"
							rows="3"
							maxlength="1000"
							placeholder="Кратко укажите причину"
							:disabled="accountActionLoading === 'purge'"
						/>
					</label>
					<p v-if="deleteConfirm.error" class="cp-form-error" role="alert">
						{{ deleteConfirm.error }}
					</p>
				</div>
			</template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton
						variant="outline"
						text="Отмена"
						:disabled="accountActionLoading === 'purge'"
						@click="closePermanentDelete"
					/>
					<BaseButton
						variant="danger"
						text="Удалить навсегда"
						loading-text="Удаляем…"
						:loading="accountActionLoading === 'purge'"
						@click="permanentlyDeleteConfirmed"
					/>
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

.cp-modal-stack {
	display: grid;
	gap: 14px;
}

.cp-form-error {
	margin: 0;
	color: var(--danger-color);
	font-size: 12px;
	line-height: 1.5;
}
</style>
