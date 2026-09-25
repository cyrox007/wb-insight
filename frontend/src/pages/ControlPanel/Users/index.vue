<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import CP_Users from '@/API/ControlPanel/CP_Users'
import DateTransform from '@/utils/date_transform.js'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import CreateStaffUserModal from '@/components/UserModals/create_staff_user.vue'

const router = useRouter()
const authStore = useAuthStore()

const isLoading = ref(false)
const loadError = ref('')
const users = ref([])
const total = ref(0)
const limit = ref(50)
const offset = ref(0)
const showCreateStaffModal = ref(false)
const actionUser = ref(null)
const accountAction = ref({ userId: '', kind: '' })
const deleteFlow = ref({
	isOpen: false,
	user: null,
	stage: 'confirm',
	email: '',
	error: '',
})

const filters = reactive({
	search: '',
	active: '',
	verified: '',
	staff: '',
	entity_type: '',
	role: '',
})

const sorting = reactive({
	by: 'created_at',
	order: 'desc',
})

let filterTimer = null
let loadGeneration = 0

const ENTITY_LABELS = {
	individual: 'Физ. лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юр. лицо',
}

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Админ',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь',
}

const roleOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))
const actorRoles = computed(() => authStore.user?.roles || [])
const actorIsSuperAdmin = computed(() => actorRoles.value.includes('super_admin'))
const actorCanManageUsers = computed(() =>
	actorIsSuperAdmin.value || actorRoles.value.includes('admin')
)

const hasFilters = computed(() =>
	Object.values(filters).some(value => String(value).trim() !== '')
)
const currentPage = computed(() => Math.floor(offset.value / limit.value) + 1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / limit.value)))
const canGoBack = computed(() => offset.value > 0)
const canGoForward = computed(() => offset.value + users.value.length < total.value)
const visibleRange = computed(() => {
	if (!total.value || !users.value.length) return '0'
	const start = offset.value + 1
	const end = offset.value + users.value.length
	return `${start}–${end} из ${total.value}`
})

const targetIsSuperAdmin = (user) =>
	user?.roles?.some(role => role.role === 'super_admin') === true

const isSelf = (user) =>
	String(authStore.user?.id || '') === String(user?.id || '')

const canManageTarget = (user) => {
	if (!actorCanManageUsers.value || !user) return false
	if (targetIsSuperAdmin(user) && !actorIsSuperAdmin.value) return false
	return true
}

const canChangeActivity = (user) =>
	canManageTarget(user) && !isSelf(user)

const getEntityLabel = (type) => ENTITY_LABELS[type] || type || '—'
const getRoleLabel = (role) => ROLE_LABELS[role?.role] || role?.role || '—'

const getEntityVariant = (type) => {
	if (type === 'individual') return 'cp-chip--info'
	if (type === 'self_employed') return 'cp-chip--warning'
	if (type === 'legal_entity') return 'cp-chip--accent'
	return ''
}

function requestParams() {
	const params = {
		limit: limit.value,
		offset: offset.value,
		sort_by: sorting.by,
		sort_order: sorting.order,
	}
	const search = filters.search.trim()
	if (search) params.search = search
	if (filters.active !== '') params.active = filters.active === 'true'
	if (filters.verified !== '') params.verified = filters.verified === 'true'
	if (filters.staff !== '') params.staff = filters.staff === 'true'
	if (filters.entity_type) params.entity_type = filters.entity_type
	if (filters.role) params.role = filters.role
	return params
}

async function loadUsers() {
	const generation = ++loadGeneration
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Users.getUserList(requestParams())
		if (generation !== loadGeneration) return
		if (response.data?.status !== 'success' || !Array.isArray(response.data?.user_list)) {
			throw new Error('Некорректный ответ API пользователей')
		}
		users.value = response.data.user_list
		total.value = Number(response.data?.total ?? users.value.length)
		limit.value = Number(response.data?.limit ?? limit.value)
		offset.value = Number(response.data?.offset ?? offset.value)
	} catch (error) {
		if (generation !== loadGeneration) return
		console.error('Ошибка загрузки пользователей:', error)
		users.value = []
		total.value = 0
		loadError.value =
			error.response?.data?.error?.message ||
			'Не удалось загрузить список пользователей. Проверьте API панели управления.'
	} finally {
		if (generation === loadGeneration) isLoading.value = false
	}
}

function scheduleFilterReload() {
	if (filterTimer) window.clearTimeout(filterTimer)
	filterTimer = window.setTimeout(async () => {
		offset.value = 0
		await loadUsers()
	}, 300)
}

function resetFilters() {
	filters.search = ''
	filters.active = ''
	filters.verified = ''
	filters.staff = ''
	filters.entity_type = ''
	filters.role = ''
}

function toggleSort(field) {
	if (filterTimer) window.clearTimeout(filterTimer)
	if (sorting.by === field) {
		sorting.order = sorting.order === 'asc' ? 'desc' : 'asc'
	} else {
		sorting.by = field
		sorting.order = field === 'created_at' ? 'desc' : 'asc'
	}
	offset.value = 0
	loadUsers()
}

function sortIndicator(field) {
	if (sorting.by !== field) return '↕'
	return sorting.order === 'asc' ? '↑' : '↓'
}

async function previousPage() {
	if (!canGoBack.value || isLoading.value) return
	offset.value = Math.max(0, offset.value - limit.value)
	await loadUsers()
}

async function nextPage() {
	if (!canGoForward.value || isLoading.value) return
	offset.value += limit.value
	await loadUsers()
}

function openActions(user) {
	actionUser.value = user
}

function closeActions() {
	if (accountAction.value.kind) return
	actionUser.value = null
}

function openUserCard(user) {
	actionUser.value = null
	router.push({ name: 'control-panel.edit-user', params: { id: user.id } })
}

function actionLoading(user, kind) {
	return (
		accountAction.value.userId === user?.id &&
		accountAction.value.kind === kind
	)
}

async function runAccountAction(user, kind) {
	if (!canChangeActivity(user) || accountAction.value.kind) return

	accountAction.value = { userId: user.id, kind }
	loadError.value = ''
	try {
		const response = kind === 'deactivate'
			? await CP_Users.deactivateUser(user.id)
			: await CP_Users.reactivateUser(user.id, 'manual_control_panel_reactivation')

		if (response.data?.status !== 'success') {
			throw new Error(response.data?.error?.message || 'Операция не выполнена')
		}
		actionUser.value = null
		await loadUsers()
	} catch (error) {
		console.error('Ошибка изменения состояния аккаунта:', error)
		loadError.value =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось изменить состояние аккаунта.'
	} finally {
		accountAction.value = { userId: '', kind: '' }
	}
}

function openDeleteFlow(user) {
	if (!canChangeActivity(user) || accountAction.value.kind) return
	actionUser.value = null
	deleteFlow.value = {
		isOpen: true,
		user: { ...user },
		stage: user.is_active ? 'deactivate' : 'confirm',
		email: '',
		error: '',
	}
}

function closeDeleteFlow() {
	if (accountAction.value.kind) return
	deleteFlow.value = {
		isOpen: false,
		user: null,
		stage: 'confirm',
		email: '',
		error: '',
	}
}

async function deactivateForDeletion() {
	const user = deleteFlow.value.user
	if (!user || !user.is_active || accountAction.value.kind) return

	accountAction.value = { userId: user.id, kind: 'deactivate-for-delete' }
	deleteFlow.value.error = ''
	try {
		const response = await CP_Users.deactivateUser(user.id)
		if (response.data?.status !== 'success') {
			throw new Error(response.data?.error?.message || 'Не удалось деактивировать аккаунт')
		}

		deleteFlow.value.user = { ...user, is_active: false }
		deleteFlow.value.stage = 'confirm'
		await loadUsers()
	} catch (error) {
		console.error('Ошибка подготовки аккаунта к удалению:', error)
		deleteFlow.value.error =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось деактивировать аккаунт перед удалением.'
	} finally {
		accountAction.value = { userId: '', kind: '' }
	}
}

async function permanentlyDeleteConfirmed() {
	const user = deleteFlow.value.user
	if (!user || user.is_active || accountAction.value.kind) return

	const expectedEmail = String(user.email || '').trim().toLowerCase()
	const confirmation = String(deleteFlow.value.email || '').trim().toLowerCase()
	if (!confirmation || confirmation !== expectedEmail) {
		deleteFlow.value.error = 'Введите email пользователя точно так, как он указан выше.'
		return
	}

	accountAction.value = { userId: user.id, kind: 'purge' }
	deleteFlow.value.error = ''
	try {
		const response = await CP_Users.permanentlyDeleteUser(
			user.id,
			confirmation,
			'Удаление из списка пользователей',
		)
		if (response.data?.status !== 'success' || response.data?.deleted !== true) {
			throw new Error(response.data?.error?.message || 'Пользователь не удалён')
		}
		deleteFlow.value = {
			isOpen: false,
			user: null,
			stage: 'confirm',
			email: '',
			error: '',
		}
		await loadUsers()
	} catch (error) {
		console.error('Ошибка необратимого удаления пользователя:', error)
		deleteFlow.value.error =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось удалить пользователя.'
	} finally {
		accountAction.value = { userId: '', kind: '' }
	}
}

async function handleStaffCreated() {
	offset.value = 0
	await loadUsers()
}

watch(
	() => [
		filters.search,
		filters.active,
		filters.verified,
		filters.staff,
		filters.entity_type,
		filters.role,
	],
	scheduleFilterReload,
)

watch(limit, async () => {
	offset.value = 0
	await loadUsers()
})

onMounted(loadUsers)

onBeforeUnmount(() => {
	if (filterTimer) window.clearTimeout(filterTimer)
})
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Аккаунты</p>
				<h2 class="cp-detail-title">Пользователи</h2>
				<p class="cp-subtitle">Фильтры применяются автоматически. Нажмите заголовок колонки, чтобы изменить сортировку.</p>
			</div>
			<BaseButton
				v-if="actorIsSuperAdmin"
				variant="primary"
				text="Добавить сотрудника"
				@click="showCreateStaffModal = true"
			/>
		</header>

		<div class="cp-card cp-filter-surface user-filters">
			<label class="cp-field-label user-search">
				<span>Поиск</span>
				<input
					v-model="filters.search"
					type="search"
					maxlength="100"
					placeholder="Имя, email, телефон, ID, ИНН, отдел или должность"
					autocomplete="off"
				/>
			</label>

			<label class="cp-field-label">
				<span>Активность</span>
				<select v-model="filters.active">
					<option value="">Все</option>
					<option value="true">Активные</option>
					<option value="false">Неактивные</option>
				</select>
			</label>

			<label class="cp-field-label">
				<span>Email</span>
				<select v-model="filters.verified">
					<option value="">Любой статус</option>
					<option value="true">Подтверждён</option>
					<option value="false">Не подтверждён</option>
				</select>
			</label>

			<label class="cp-field-label">
				<span>Контур</span>
				<select v-model="filters.staff">
					<option value="">Все</option>
					<option value="false">Клиенты</option>
					<option value="true">Сотрудники</option>
				</select>
			</label>

			<label class="cp-field-label">
				<span>Тип</span>
				<select v-model="filters.entity_type">
					<option value="">Все</option>
					<option value="individual">Физ. лицо</option>
					<option value="self_employed">Самозанятый</option>
					<option value="legal_entity">Юр. лицо</option>
				</select>
			</label>

			<label class="cp-field-label">
				<span>Роль</span>
				<select v-model="filters.role">
					<option value="">Все роли</option>
					<option v-for="item in roleOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
				</select>
			</label>

			<div class="cp-filter-surface__actions">
				<BaseButton
					type="button"
					variant="outline"
					size="small"
					text="Сбросить"
					:disabled="!hasFilters || isLoading"
					@click="resetFilters"
				/>
			</div>
		</div>

		<div v-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadUsers" />
			</div>
		</div>

		<div v-else class="cp-table-wrap">
			<div class="cp-table__toolbar user-table-toolbar">
				<div>
					<strong>{{ hasFilters ? 'Результаты фильтра' : 'Все пользователи' }}</strong>
					<span class="cp-table__count">{{ isLoading ? 'Обновляем…' : visibleRange }}</span>
				</div>
				<label class="user-page-size">
					<span>На странице</span>
					<select v-model.number="limit" :disabled="isLoading">
						<option :value="25">25</option>
						<option :value="50">50</option>
						<option :value="100">100</option>
						<option :value="200">200</option>
					</select>
				</label>
			</div>

			<div v-if="isLoading && !users.length" class="cp-state" role="status">
				Загружаем пользователей…
			</div>

			<div v-else-if="users.length === 0" class="cp-state">
				<strong>{{ hasFilters ? 'По выбранным условиям пользователей не найдено.' : 'Пользователей пока нет.' }}</strong>
				<span v-if="hasFilters">Измените фильтры или сбросьте их.</span>
			</div>

			<div v-else class="cp-table-scroll" role="region" aria-label="Таблица пользователей" tabindex="0">
				<table class="cp-table users-table">
					<caption class="cp-sr-only">Пользователи, контакты, тип аккаунта, роли, статус, регистрация и действия.</caption>
					<colgroup>
						<col class="col-user" />
						<col class="col-email" />
						<col class="col-phone" />
						<col class="col-access" />
						<col class="col-status" />
						<col class="col-created" />
						<col class="col-actions" />
					</colgroup>
					<thead>
						<tr>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('user')">
									Пользователь <span>{{ sortIndicator('user') }}</span>
								</button>
							</th>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('email')">
									Email <span>{{ sortIndicator('email') }}</span>
								</button>
							</th>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('phone')">
									Телефон <span>{{ sortIndicator('phone') }}</span>
								</button>
							</th>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('entity_type')">
									Аккаунт <span>{{ sortIndicator('entity_type') }}</span>
								</button>
							</th>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('status')">
									Статус <span>{{ sortIndicator('status') }}</span>
								</button>
							</th>
							<th scope="col">
								<button class="sort-button" type="button" @click="toggleSort('created_at')">
									Регистрация <span>{{ sortIndicator('created_at') }}</span>
								</button>
							</th>
							<th scope="col">Действия</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="user in users" :key="user.id">
							<td>
								<div class="cp-person">
									<div class="cp-avatar" aria-hidden="true">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
									<div class="user-identity">
										<button class="user-name-link" type="button" @click="openUserCard(user)">
											{{ user.full_name || 'Не указано' }}
										</button>
										<code class="cp-code" :title="user.id">{{ user.id.substring(0, 8) }}…</code>
										<span v-if="user.staff_id" class="cp-muted">{{ user.staff_id }}</span>
									</div>
								</div>
							</td>
							<td class="breakable-cell">{{ user.email }}</td>
							<td class="nowrap-cell">{{ user.phone || '—' }}</td>
							<td>
								<div class="account-cell">
									<span class="cp-chip" :class="getEntityVariant(user.entity_type)">
										{{ getEntityLabel(user.entity_type) }}
									</span>
									<div class="cp-chip-row">
										<span v-for="role in user.roles" :key="role.role" class="cp-chip cp-chip--accent">
											{{ getRoleLabel(role) }}
										</span>
										<span v-if="!user.roles?.length" class="cp-muted">Роли не назначены</span>
									</div>
								</div>
							</td>
							<td>
								<div class="status-cell">
									<span class="cp-chip" :class="user.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
										{{ user.is_active ? 'Активен' : 'Неактивен' }}
									</span>
									<span class="cp-chip" :class="user.email_verified_at ? 'cp-chip--active' : 'cp-chip--warning'">
										{{ user.email_verified_at ? 'Email ✓' : 'Email не подтверждён' }}
									</span>
								</div>
							</td>
							<td class="nowrap-cell">{{ DateTransform.formatDate(user.created_at) }}</td>
							<td>
								<BaseButton
									variant="outline"
									size="small"
									text="Действия"
									:disabled="Boolean(accountAction.kind)"
									@click="openActions(user)"
								/>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div v-if="total > 0" class="user-pagination" aria-label="Постраничная навигация">
				<span class="user-pagination__meta">Страница {{ currentPage }} из {{ pageCount }}</span>
				<div class="user-pagination__actions">
					<BaseButton variant="outline" size="small" text="Назад" :disabled="!canGoBack || isLoading" @click="previousPage" />
					<BaseButton variant="outline" size="small" text="Дальше" :disabled="!canGoForward || isLoading" @click="nextPage" />
				</div>
			</div>
		</div>

		<CreateStaffUserModal
			v-if="showCreateStaffModal"
			:is-open="true"
			@close="showCreateStaffModal = false"
			@created="handleStaffCreated"
		/>

		<Modal
			v-if="actionUser"
			:is-open="true"
			aria-label="Действия с пользователем"
			:close-on-overlay-click="!accountAction.kind"
			:close-on-escape="!accountAction.kind"
			@close="closeActions"
		>
			<template #header>
				<div>
					<h3 class="cp-modal-title">{{ actionUser.full_name || actionUser.email }}</h3>
					<p class="cp-muted">{{ actionUser.email }}</p>
				</div>
			</template>
			<template #body>
				<div class="action-menu">
					<BaseButton variant="outline" text="Открыть карточку" @click="openUserCard(actionUser)" />
					<BaseButton
						v-if="canChangeActivity(actionUser) && actionUser.is_active"
						variant="outline"
						text="Деактивировать"
						loading-text="Деактивируем…"
						:loading="actionLoading(actionUser, 'deactivate')"
						:disabled="Boolean(accountAction.kind)"
						@click="runAccountAction(actionUser, 'deactivate')"
					/>
					<BaseButton
						v-if="canChangeActivity(actionUser) && !actionUser.is_active"
						variant="success"
						text="Активировать"
						loading-text="Активируем…"
						:loading="actionLoading(actionUser, 'reactivate')"
						:disabled="Boolean(accountAction.kind)"
						@click="runAccountAction(actionUser, 'reactivate')"
					/>
					<BaseButton
						v-if="canChangeActivity(actionUser)"
						variant="danger"
						text="Удалить…"
						:disabled="Boolean(accountAction.kind)"
						@click="openDeleteFlow(actionUser)"
					/>
					<p v-if="canChangeActivity(actionUser)" class="delete-algorithm">
						Удаление выполняется в два шага: активный аккаунт сначала деактивируется и теряет доступ, затем после подтверждения email удаляется необратимо.
					</p>
					<p v-else-if="isSelf(actionUser)" class="cp-muted">
						Собственный аккаунт нельзя деактивировать или удалить из административного списка.
					</p>
				</div>
			</template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton variant="outline" text="Закрыть" :disabled="Boolean(accountAction.kind)" @click="closeActions" />
				</div>
			</template>
		</Modal>

		<Modal
			v-if="deleteFlow.isOpen"
			:is-open="true"
			aria-label="Удаление пользователя"
			:close-on-overlay-click="!accountAction.kind"
			:close-on-escape="!accountAction.kind"
			@close="closeDeleteFlow"
		>
			<template #header>
				<div>
					<h3 class="cp-modal-title">Удалить пользователя</h3>
					<p class="cp-muted">{{ deleteFlow.user?.email }}</p>
				</div>
			</template>
			<template #body>
				<div class="delete-flow">
					<template v-if="deleteFlow.stage === 'deactivate'">
						<div class="delete-step">
							<span class="delete-step__number">1</span>
							<div>
								<strong>Сначала деактивировать аккаунт</strong>
								<p>Пользователь перестанет входить в систему, а его активные сессии будут отозваны. Данные на этом шаге ещё не удаляются.</p>
							</div>
						</div>
						<div class="delete-step delete-step--muted">
							<span class="delete-step__number">2</span>
							<div>
								<strong>Затем удалить навсегда</strong>
								<p>После деактивации потребуется ввести email для подтверждения необратимого удаления.</p>
							</div>
						</div>
					</template>

					<template v-else>
						<div class="delete-step delete-step--done">
							<span class="delete-step__number">✓</span>
							<div>
								<strong>Аккаунт деактивирован</strong>
								<p>Авторизация уже отключена. Теперь можно выполнить необратимое удаление.</p>
							</div>
						</div>
						<div class="delete-step">
							<span class="delete-step__number">2</span>
							<div>
								<strong>Подтвердите удаление</strong>
								<p>Введите email <b>{{ deleteFlow.user?.email }}</b>. После удаления восстановить аккаунт через интерфейс нельзя.</p>
							</div>
						</div>
						<label class="cp-field-label">
							<span>Email для подтверждения</span>
							<input
								v-model="deleteFlow.email"
								type="email"
								autocomplete="off"
								:placeholder="deleteFlow.user?.email || ''"
								:disabled="accountAction.kind === 'purge'"
							/>
						</label>
					</template>

					<p v-if="deleteFlow.error" class="delete-error" role="alert">{{ deleteFlow.error }}</p>
				</div>
			</template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton
						variant="outline"
						text="Отмена"
						:disabled="Boolean(accountAction.kind)"
						@click="closeDeleteFlow"
					/>
					<BaseButton
						v-if="deleteFlow.stage === 'deactivate'"
						variant="danger"
						text="Деактивировать и продолжить"
						loading-text="Деактивируем…"
						:loading="accountAction.kind === 'deactivate-for-delete'"
						@click="deactivateForDeletion"
					/>
					<BaseButton
						v-else
						variant="danger"
						text="Удалить навсегда"
						loading-text="Удаляем…"
						:loading="accountAction.kind === 'purge'"
						@click="permanentlyDeleteConfirmed"
					/>
				</div>
			</template>
		</Modal>
	</section>
</template>

<style scoped>
.user-filters {
	grid-template-columns: minmax(250px, 1.55fr) repeat(5, minmax(125px, .72fr)) auto;
}

.user-search {
	min-width: 0;
}

.user-table-toolbar > div {
	min-width: 0;
	display: flex;
	align-items: baseline;
	gap: 10px;
	flex-wrap: wrap;
}

.user-page-size {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	color: var(--text-muted);
	font-size: 12px;
	font-weight: 650;
}

.user-page-size select {
	width: auto;
	min-width: 76px;
	min-height: 34px;
	padding: 6px 28px 6px 8px;
}

.users-table {
	width: 100%;
	min-width: 980px;
}

.col-user { width: 17%; }
.col-email { width: 17%; }
.col-phone { width: 12%; }
.col-access { width: 17%; }
.col-status { width: 15%; }
.col-created { width: 13%; }
.col-actions { width: 9%; }

.sort-button {
	display: inline-flex;
	align-items: center;
	gap: 5px;
	padding: 0;
	border: 0;
	background: transparent;
	color: inherit;
	font: inherit;
	font-weight: inherit;
	text-transform: inherit;
	cursor: pointer;
}

.sort-button span {
	color: var(--text-muted);
	font-size: 12px;
}

.sort-button:hover,
.sort-button:focus-visible {
	color: var(--secondary-color);
}

.user-identity {
	min-width: 0;
	display: grid;
	gap: 3px;
}

.user-name-link {
	padding: 0;
	border: 0;
	background: transparent;
	color: var(--text-color);
	font: inherit;
	font-weight: 700;
	text-align: left;
	cursor: pointer;
}

.user-name-link:hover,
.user-name-link:focus-visible {
	color: var(--secondary-color);
	text-decoration: underline;
}

.breakable-cell {
	overflow-wrap: anywhere;
}

.nowrap-cell {
	white-space: nowrap;
}

.account-cell,
.status-cell {
	display: grid;
	justify-items: start;
	gap: 6px;
}

.action-menu {
	display: grid;
	gap: 9px;
}

.action-menu :deep(.base-button) {
	width: 100%;
}

.delete-algorithm {
	margin: 4px 0 0;
	padding: 10px 12px;
	border-radius: 9px;
	background: var(--light-bg);
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.5;
}

.delete-flow {
	display: grid;
	gap: 14px;
}

.delete-step {
	display: grid;
	grid-template-columns: 30px minmax(0, 1fr);
	gap: 10px;
	align-items: start;
	padding: 12px;
	border: 1px solid var(--border-color);
	border-radius: 10px;
	background: var(--card-bg);
}

.delete-step--muted {
	opacity: .68;
}

.delete-step--done {
	border-color: color-mix(in srgb, var(--success-color) 35%, var(--border-color));
	background: color-mix(in srgb, var(--success-color) 6%, var(--card-bg));
}

.delete-step__number {
	display: inline-grid;
	place-items: center;
	width: 28px;
	height: 28px;
	border-radius: 50%;
	background: var(--light-bg);
	font-size: 12px;
	font-weight: 800;
}

.delete-step strong {
	font-size: 13px;
}

.delete-step p {
	margin: 4px 0 0;
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.5;
}

.delete-error {
	margin: 0;
	color: var(--danger-color);
	font-size: 12px;
	line-height: 1.5;
}

.user-pagination {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	padding: 12px 16px;
	border-top: 1px solid var(--border-color);
	background: var(--card-bg);
}

.user-pagination__meta {
	color: var(--text-muted);
	font-size: 12px;
}

.user-pagination__actions {
	display: flex;
	gap: 8px;
}

@media (max-width: 1180px) {
	.user-filters {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.user-search {
		grid-column: span 2;
	}
}

@media (max-width: 760px) {
	.user-filters {
		grid-template-columns: 1fr;
	}

	.user-search {
		grid-column: auto;
	}

	.user-table-toolbar,
	.user-pagination {
		align-items: stretch;
		flex-direction: column;
	}

	.user-page-size {
		justify-content: space-between;
	}

	.user-pagination__actions {
		width: 100%;
	}

	.user-pagination__actions :deep(.base-button) {
		flex: 1 1 0;
	}
}
</style>
