<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import Modal from '@/components/UI/Modal.vue'

const props = defineProps({
	isOpen: Boolean,
	user: {
		type: Object,
		default: null,
	},
	currentUserId: {
		type: String,
		default: '',
	},
})

const emit = defineEmits(['close', 'changed'])

const roles = ref([])
const canManageRoles = ref(false)
const isLoading = ref(false)
const isSaving = ref(false)
const selectedRole = ref('')
const confirmEmail = ref('')
const pendingRemoveRole = ref('')
const formMessage = ref('')

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь',
}

const ROLE_DESCRIPTIONS = {
	super_admin: 'Полный системный доступ, управление ролями и критическими настройками.',
	admin: 'Управление пользователями и тарифами, просмотр платежей, аудита и рассылок.',
	manager: 'Просмотр операционных разделов без изменения критических данных.',
	support: 'Работа с пользовательскими карточками и аудитом без административных write-операций.',
	analyst: 'Операционная сводка без доступа к персональным карточкам и критическим настройкам.',
	user: 'Базовый клиентский доступ без панели управления.',
}

const currentRoleCodes = computed(() =>
	(props.user?.roles || []).map(item => item.role)
)

const assignableRoles = computed(() =>
	roles.value.filter(role => !currentRoleCodes.value.includes(role.code))
)

const selectedRoleDefinition = computed(() =>
	roles.value.find(role => role.code === selectedRole.value) || null
)

const isSelf = computed(() =>
	Boolean(props.user?.id) &&
	String(props.user.id) === String(props.currentUserId || '')
)

const isSuperAdminSelection = computed(() =>
	selectedRole.value === 'super_admin'
)

const superAdminConfirmationValid = computed(() => {
	if (!isSuperAdminSelection.value) return true
	const expected = String(props.user?.email || '').trim().toLowerCase()
	const actual = String(confirmEmail.value || '').trim().toLowerCase()
	return Boolean(expected && actual && expected === actual)
})

const canSubmitAssignment = computed(() =>
	canManageRoles.value &&
	Boolean(selectedRole.value) &&
	!isSaving.value &&
	superAdminConfirmationValid.value
)

const roleLabel = (role) => ROLE_LABELS[role] || role

function canRemoveRole(role) {
	if (!canManageRoles.value || isSaving.value) return false
	if (role === 'user') return false
	if (role === 'super_admin' && isSelf.value) return false
	return true
}

function resetLocalState() {
	selectedRole.value = ''
	confirmEmail.value = ''
	pendingRemoveRole.value = ''
	formMessage.value = ''
}

async function loadRoles() {
	if (!props.isOpen) return

	isLoading.value = true
	formMessage.value = ''
	try {
		const response = await CP_Roles.getRolesList()
		if (response.data?.status !== 'success' || !Array.isArray(response.data?.roles)) {
			throw new Error('Некорректный ответ API ролей')
		}
		roles.value = response.data.roles
		canManageRoles.value = Boolean(response.data.can_manage)
	} catch (error) {
		console.error('Ошибка загрузки ролей:', error)
		roles.value = []
		canManageRoles.value = false
		formMessage.value =
			error.response?.data?.error?.message ||
			'Не удалось загрузить роли.'
	} finally {
		isLoading.value = false
	}
}

async function assignRole() {
	if (!canSubmitAssignment.value || !props.user?.id) return

	isSaving.value = true
	formMessage.value = ''
	try {
		const confirmation = isSuperAdminSelection.value
			? confirmEmail.value.trim()
			: null
		const response = await CP_Roles.assignRoleToUser(
			props.user.id,
			selectedRole.value,
			confirmation,
		)
		if (response.data?.status !== 'success') {
			throw new Error(
				response.data?.error?.message ||
				response.data?.message ||
				'Не удалось добавить роль'
			)
		}
		emit('changed')
		emit('close')
	} catch (error) {
		console.error('Ошибка назначения роли:', error)
		formMessage.value =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось добавить роль.'
	} finally {
		isSaving.value = false
	}
}

function askRemoveRole(role) {
	if (!canRemoveRole(role)) return
	pendingRemoveRole.value = role
	formMessage.value = ''
}

function cancelRemoveRole() {
	if (isSaving.value) return
	pendingRemoveRole.value = ''
	formMessage.value = ''
}

async function removeRole() {
	const role = pendingRemoveRole.value
	if (!role || !canRemoveRole(role) || !props.user?.id) return

	isSaving.value = true
	formMessage.value = ''
	try {
		const response = await CP_Roles.deleteRoleFromUser(props.user.id, role)
		if (response.data?.status !== 'success') {
			throw new Error(
				response.data?.error?.message ||
				response.data?.message ||
				'Не удалось снять роль'
			)
		}
		emit('changed')
		emit('close')
	} catch (error) {
		console.error('Ошибка снятия роли:', error)
		formMessage.value =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось снять роль.'
	} finally {
		isSaving.value = false
	}
}

onMounted(loadRoles)

watch(
	() => props.isOpen,
	(isOpen) => {
		if (!isOpen) return
		resetLocalState()
		loadRoles()
	},
)
</script>

<template>
	<Modal
		:is-open="isOpen"
		size="large"
		aria-label="Изменение ролей пользователя"
		:close-on-overlay-click="!isSaving"
		:close-on-escape="!isSaving"
		@close="$emit('close')"
	>
		<template #header>
			<div>
				<h3 class="cp-modal-title">Изменить роли</h3>
				<p class="cp-muted">
					{{ user?.full_name || user?.email || 'Пользователь' }}
					<span v-if="user?.email"> · {{ user.email }}</span>
				</p>
			</div>
		</template>

		<template #body>
			<div class="roles-notice">
				<strong>Роли суммируются.</strong>
				<span>Добавление новой роли не заменяет текущие. Сначала смотрите блок «Текущие роли», затем выбирайте конкретное действие.</span>
			</div>

			<div v-if="isLoading" class="cp-state" role="status">
				Загружаем роли…
			</div>

			<template v-else>
				<section class="role-section">
					<div class="role-section__head">
						<div>
							<h4>Текущие роли</h4>
							<p>Это роли, которые назначены пользователю прямо сейчас.</p>
						</div>
						<span class="cp-muted">{{ currentRoleCodes.length }} ролей</span>
					</div>

					<div v-if="currentRoleCodes.length" class="current-role-list">
						<div v-for="role in currentRoleCodes" :key="role" class="current-role-row">
							<div>
								<strong>{{ roleLabel(role) }}</strong>
								<span>{{ ROLE_DESCRIPTIONS[role] || role }}</span>
							</div>
							<div>
								<BaseButton
									v-if="canRemoveRole(role) && pendingRemoveRole !== role"
									variant="outline"
									size="small"
									text="Снять роль"
									:disabled="isSaving"
									@click="askRemoveRole(role)"
								/>
								<span v-else-if="role === 'user'" class="role-protection">
									Базовая роль
								</span>
								<span v-else-if="role === 'super_admin' && isSelf" class="role-protection">
									Свою роль снять нельзя
								</span>
							</div>

							<div v-if="pendingRemoveRole === role" class="remove-confirm">
								<div>
									<strong>Подтвердите снятие роли «{{ roleLabel(role) }}»</strong>
									<p>Доступ пользователя изменится сразу после операции.</p>
								</div>
								<div class="remove-confirm__actions">
									<BaseButton
										variant="outline"
										size="small"
										text="Отмена"
										:disabled="isSaving"
										@click="cancelRemoveRole"
									/>
									<BaseButton
										variant="danger"
										size="small"
										text="Снять роль"
										loading-text="Снимаем…"
										:loading="isSaving"
										@click="removeRole"
									/>
								</div>
							</div>
						</div>
					</div>
					<div v-else class="cp-state cp-state--compact">
						Роли не назначены.
					</div>
				</section>

				<section v-if="canManageRoles" class="role-section role-section--add">
					<div class="role-section__head">
						<div>
							<h4>Добавить ещё одну роль</h4>
							<p>Ничего не меняется, пока вы явно не выбрали роль и не нажали «Добавить роль».</p>
						</div>
					</div>

					<div v-if="assignableRoles.length" class="role-add-form">
						<label class="cp-field-label">
							<span>Новая роль</span>
							<select v-model="selectedRole" class="cp-form-select" :disabled="isSaving">
								<option value="">Выберите роль</option>
								<option
									v-for="role in assignableRoles"
									:key="role.code"
									:value="role.code"
								>
									{{ roleLabel(role.code) }}
								</option>
							</select>
						</label>

						<div v-if="selectedRoleDefinition" class="selected-role-preview">
							<strong>{{ roleLabel(selectedRoleDefinition.code) }}</strong>
							<span>{{ ROLE_DESCRIPTIONS[selectedRoleDefinition.code] || selectedRoleDefinition.code }}</span>
							<small>{{ selectedRoleDefinition.permissions?.length || 0 }} административных прав</small>
						</div>

						<div v-if="isSuperAdminSelection" class="super-admin-confirm">
							<strong>Полный системный доступ</strong>
							<p>
								Эта роль позволяет управлять ролями и критическими настройками.
								Для подтверждения введите email пользователя:
								<b>{{ user?.email }}</b>
							</p>
							<label class="cp-field-label">
								<span>Email для подтверждения</span>
								<input
									v-model="confirmEmail"
									type="email"
									autocomplete="off"
									:placeholder="user?.email || ''"
									:disabled="isSaving"
								/>
							</label>
						</div>

						<BaseButton
							variant="primary"
							text="Добавить роль"
							loading-text="Добавляем…"
							:loading="isSaving"
							:disabled="!canSubmitAssignment"
							@click="assignRole"
						/>
					</div>
					<div v-else class="cp-muted">
						Пользователю уже назначены все доступные системные роли.
					</div>
				</section>

				<div v-if="!canManageRoles" class="cp-state cp-state--compact">
					Роли доступны только для просмотра. Изменение требует права <code>roles:write</code>.
				</div>
			</template>

			<FormMessage
				v-if="formMessage"
				:message="formMessage"
				message-type="error"
			/>
		</template>

		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton
					variant="outline"
					text="Закрыть"
					:disabled="isSaving"
					@click="$emit('close')"
				/>
			</div>
		</template>
	</Modal>
</template>

<style scoped>
.roles-notice {
	margin-bottom: 14px;
	padding: 12px 14px;
	display: grid;
	gap: 4px;
	border: 1px solid color-mix(in srgb, var(--secondary-color) 28%, var(--border-color));
	border-radius: 10px;
	background: color-mix(in srgb, var(--secondary-color) 7%, var(--card-bg));
}

.roles-notice strong,
.role-section h4 {
	color: var(--text-color);
	font-size: 13px;
}

.roles-notice span,
.role-section__head p,
.current-role-row span,
.selected-role-preview span,
.super-admin-confirm p {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.5;
}

.role-section {
	display: grid;
	gap: 10px;
	padding: 14px 0;
	border-top: 1px solid var(--border-color);
}

.role-section:first-of-type {
	border-top: 0;
}

.role-section__head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
}

.role-section__head h4,
.role-section__head p {
	margin: 0;
}

.current-role-list {
	display: grid;
	gap: 8px;
}

.current-role-row {
	padding: 10px 12px;
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	gap: 8px 12px;
	align-items: center;
	border: 1px solid var(--border-color);
	border-radius: 9px;
	background: var(--card-bg);
}

.current-role-row > div:first-child {
	min-width: 0;
	display: grid;
	gap: 3px;
}

.role-protection {
	padding: 5px 8px;
	border-radius: 999px;
	background: var(--light-bg);
	color: var(--text-subtle) !important;
	font-size: 10px !important;
	font-weight: 700;
}

.remove-confirm {
	grid-column: 1 / -1;
	padding-top: 9px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	border-top: 1px solid var(--border-color);
}

.remove-confirm p {
	margin: 3px 0 0;
	color: var(--text-muted);
	font-size: 11px;
}

.remove-confirm__actions {
	display: flex;
	gap: 7px;
}

.role-add-form {
	display: grid;
	gap: 10px;
}

.selected-role-preview,
.super-admin-confirm {
	padding: 11px 12px;
	display: grid;
	gap: 4px;
	border: 1px solid var(--border-color);
	border-radius: 9px;
	background: var(--light-bg);
}

.selected-role-preview small {
	color: var(--text-subtle);
	font-size: 10px;
}

.super-admin-confirm {
	border-color: color-mix(in srgb, var(--danger-color) 35%, var(--border-color));
	background: color-mix(in srgb, var(--danger-color) 6%, var(--card-bg));
}

.super-admin-confirm p {
	margin: 0;
}

.cp-state--compact {
	min-height: auto;
	padding: 10px 12px;
}

@media (max-width: 640px) {
	.current-role-row {
		grid-template-columns: 1fr;
	}

	.remove-confirm {
		align-items: stretch;
		flex-direction: column;
	}

	.remove-confirm__actions {
		width: 100%;
	}

	.remove-confirm__actions :deep(.base-button) {
		flex: 1 1 0;
	}
}
</style>
