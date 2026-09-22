<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CP_Users from '@/API/ControlPanel/CP_Users'
import DateTransform from '@/utils/date_transform.js'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const isLoading = ref(false)
const loadError = ref('')
const users = ref([])
const total = ref(0)
const limit = ref(50)
const offset = ref(0)

const filters = reactive({
	search: '',
	active: '',
	verified: '',
	staff: '',
	role: '',
})

const ENTITY_LABELS = {
	individual: 'Физ. лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юр. лицо'
}

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Админ',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
}

const roleOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))

const getEntityLabel = (type) => ENTITY_LABELS[type] || type || '—'
const getRoleLabel = (role) => ROLE_LABELS[role?.role] || role?.role || '—'

const getEntityVariant = (type) => {
	if (type === 'individual') return 'cp-chip--info'
	if (type === 'self_employed') return 'cp-chip--warning'
	if (type === 'legal_entity') return 'cp-chip--accent'
	return ''
}

const hasFilters = computed(() => Object.values(filters).some(value => String(value).trim() !== ''))
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

function requestParams() {
	const params = {
		limit: limit.value,
		offset: offset.value,
	}
	const search = filters.search.trim()
	if (search) params.search = search
	if (filters.active !== '') params.active = filters.active === 'true'
	if (filters.verified !== '') params.verified = filters.verified === 'true'
	if (filters.staff !== '') params.staff = filters.staff === 'true'
	if (filters.role) params.role = filters.role
	return params
}

async function loadUsers() {
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Users.getUserList(requestParams())
		if (response.data?.status !== 'success' || !Array.isArray(response.data?.user_list)) {
			throw new Error('Некорректный ответ API пользователей')
		}
		users.value = response.data.user_list
		total.value = Number(response.data?.total ?? users.value.length)
		limit.value = Number(response.data?.limit ?? limit.value)
		offset.value = Number(response.data?.offset ?? offset.value)
	} catch (error) {
		console.error('Error fetching users:', error)
		users.value = []
		total.value = 0
		loadError.value = error.response?.data?.error?.message || 'Не удалось загрузить список пользователей. Проверьте API панели управления.'
	} finally {
		isLoading.value = false
	}
}

async function applyFilters() {
	offset.value = 0
	await loadUsers()
}

async function resetFilters() {
	filters.search = ''
	filters.active = ''
	filters.verified = ''
	filters.staff = ''
	filters.role = ''
	offset.value = 0
	await loadUsers()
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

async function changePageSize() {
	offset.value = 0
	await loadUsers()
}

onMounted(loadUsers)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Аккаунты</p>
				<h2 class="cp-detail-title">Пользователи</h2>
				<p class="cp-subtitle">Поиск, фильтрация и просмотр зарегистрированных аккаунтов без загрузки всей базы в браузер.</p>
			</div>
		</header>

		<form class="cp-card cp-filter-surface user-filters" @submit.prevent="applyFilters">
			<label class="cp-field-label user-search">
				<span>Поиск</span>
				<input
					v-model="filters.search"
					type="search"
					maxlength="100"
					placeholder="Имя, email, телефон или staff ID"
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
				<span>Тип аккаунта</span>
				<select v-model="filters.staff">
					<option value="">Все</option>
					<option value="false">Клиенты</option>
					<option value="true">Сотрудники</option>
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
				<BaseButton type="submit" variant="primary" size="small" text="Показать" :loading="isLoading" />
				<BaseButton type="button" variant="outline" size="small" text="Сбросить" :disabled="!hasFilters || isLoading" @click="resetFilters" />
			</div>
		</form>

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
					<select v-model.number="limit" :disabled="isLoading" @change="changePageSize">
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

			<div
				v-else
				class="cp-table-scroll"
				role="region"
				aria-label="Таблица пользователей"
				tabindex="0"
			>
				<table class="cp-table">
					<caption class="cp-sr-only">Зарегистрированные пользователи, их тип аккаунта, роли, активность, верификация и дата регистрации.</caption>
					<thead>
						<tr>
							<th scope="col">Пользователь</th>
							<th scope="col">Email</th>
							<th scope="col">Телефон</th>
							<th scope="col">Тип</th>
							<th scope="col">Роли</th>
							<th scope="col">Статус</th>
							<th scope="col">Регистрация</th>
							<th scope="col">Действия</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="user in users" :key="user.id">
							<td>
								<div class="cp-person">
									<div class="cp-avatar" aria-hidden="true">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
									<div>
										<div class="cp-person__name">{{ user.full_name || 'Не указано' }}</div>
										<code class="cp-code" :title="user.id">{{ user.id.substring(0, 8) }}…</code>
									</div>
								</div>
							</td>
							<td>{{ user.email }}</td>
							<td>{{ user.phone || '—' }}</td>
							<td>
								<span class="cp-chip" :class="getEntityVariant(user.entity_type)">
									{{ getEntityLabel(user.entity_type) }}
								</span>
							</td>
							<td>
								<div class="cp-chip-row">
									<span v-for="role in user.roles" :key="role.role" class="cp-chip cp-chip--accent">
										{{ getRoleLabel(role) }}
									</span>
									<span v-if="!user.roles?.length" class="cp-muted">—</span>
								</div>
							</td>
							<td>
								<div class="cp-chip-row">
									<span class="cp-chip" :class="user.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
										{{ user.is_active ? 'Активен' : 'Неактивен' }}
									</span>
									<span class="cp-chip" :class="user.email_verified_at ? 'cp-chip--active' : 'cp-chip--warning'">
										{{ user.email_verified_at ? 'Email ✓' : 'Email не подтверждён' }}
									</span>
								</div>
							</td>
							<td>{{ DateTransform.formatDate(user.created_at) }}</td>
							<td>
								<button
									class="cp-icon-button"
									type="button"
									@click="$router.push({ name: 'control-panel.edit-user', params: { id: user.id } })"
									title="Открыть карточку"
									:aria-label="`Открыть карточку пользователя ${user.full_name || user.email}`"
								>
									<svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
										<path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
									</svg>
								</button>
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
	</section>
</template>

<style scoped>
.user-filters {
	grid-template-columns: minmax(240px, 1.5fr) repeat(4, minmax(145px, .8fr)) auto;
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
