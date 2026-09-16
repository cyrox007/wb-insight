<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CP_Audit from '@/API/ControlPanel/CP_Audit'

const events = ref([])
const total = ref(0)
const limit = 50
const offset = ref(0)
const isLoading = ref(false)
const loadError = ref('')
const selected = ref(null)
const detailLoading = ref(false)

const filters = reactive({
	action: '',
	result: '',
	target_type: '',
	request_id: '',
	actor_id: '',
	date_from: '',
	date_to: '',
})

const pageStart = computed(() => total.value === 0 ? 0 : offset.value + 1)
const pageEnd = computed(() => Math.min(offset.value + limit, total.value))
const hasPrevious = computed(() => offset.value > 0)
const hasNext = computed(() => offset.value + limit < total.value)

function resultLabel(value) {
	return ({ success: 'Успешно', denied: 'Отклонено', failed: 'Ошибка' }[value] || value)
}

function resultClass(value) {
	return {
		'cp-chip--active': value === 'success',
		'cp-chip--warning': value === 'denied',
		'cp-chip--inactive': value === 'failed',
	}
}

function formatDate(value) {
	return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function requestParams() {
	const params = { limit, offset: offset.value }
	for (const key of ['action', 'result', 'target_type', 'request_id', 'actor_id']) {
		if (filters[key]) params[key] = filters[key].trim()
	}
	if (filters.date_from) params.date_from = new Date(filters.date_from).toISOString()
	if (filters.date_to) params.date_to = new Date(filters.date_to).toISOString()
	return params
}

async function loadEvents() {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Audit.getEvents(requestParams())
		if (data?.status !== 'success' || !Array.isArray(data?.events)) throw new Error('Некорректный ответ API')
		events.value = data.events
		total.value = Number(data.pagination?.total || 0)
	} catch (error) {
		console.error('Ошибка загрузки аудита:', error)
		loadError.value = error.response?.data?.error?.message || 'Не удалось загрузить журнал аудита.'
	} finally {
		isLoading.value = false
	}
}

function applyFilters() {
	offset.value = 0
	selected.value = null
	loadEvents()
}

function resetFilters() {
	Object.assign(filters, { action: '', result: '', target_type: '', request_id: '', actor_id: '', date_from: '', date_to: '' })
	applyFilters()
}

function previousPage() {
	if (!hasPrevious.value) return
	offset.value = Math.max(0, offset.value - limit)
	selected.value = null
	loadEvents()
}

function nextPage() {
	if (!hasNext.value) return
	offset.value += limit
	selected.value = null
	loadEvents()
}

async function openEvent(event) {
	detailLoading.value = true
	try {
		const { data } = await CP_Audit.getEvent(event.id)
		if (data?.status !== 'success' || !data?.event) throw new Error('Некорректный ответ API')
		selected.value = data.event
	} catch (error) {
		console.error('Ошибка загрузки события аудита:', error)
		loadError.value = 'Не удалось загрузить детали события.'
	} finally {
		detailLoading.value = false
	}
}

onMounted(loadEvents)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Безопасность и инциденты</p>
				<h2 class="cp-detail-title">Аудит действий</h2>
				<p class="cp-subtitle">Append-only журнал значимых пользовательских и административных действий с request-корреляцией.</p>
			</div>
		</header>

		<div class="audit-filters cp-card">
			<input v-model.trim="filters.action" class="filter-input" type="search" placeholder="Действие / префикс">
			<select v-model="filters.result" class="filter-input">
				<option value="">Любой результат</option>
				<option value="success">Успешно</option>
				<option value="denied">Отклонено</option>
				<option value="failed">Ошибка</option>
			</select>
			<input v-model.trim="filters.target_type" class="filter-input" type="search" placeholder="Тип объекта">
			<input v-model.trim="filters.actor_id" class="filter-input" type="search" placeholder="ID пользователя">
			<input v-model.trim="filters.request_id" class="filter-input" type="search" placeholder="Request ID">
			<input v-model="filters.date_from" class="filter-input" type="datetime-local" aria-label="Дата от">
			<input v-model="filters.date_to" class="filter-input" type="datetime-local" aria-label="Дата до">
			<div class="audit-filter-actions">
				<BaseButton variant="primary" size="small" text="Применить" @click="applyFilters" />
				<BaseButton variant="outline" size="small" text="Сбросить" @click="resetFilters" />
			</div>
		</div>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем журнал аудита…</div>
		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadEvents" />
			</div>
		</div>
		<div v-else-if="events.length === 0" class="cp-state">По выбранным условиям событий нет.</div>
		<div v-else class="cp-table-wrap">
			<div class="cp-table-scroll">
				<table class="cp-table audit-table">
					<thead>
						<tr><th>Время</th><th>Пользователь</th><th>Действие</th><th>Объект</th><th>Результат</th><th>Источник</th><th>Request ID</th><th></th></tr>
					</thead>
					<tbody>
						<tr v-for="event in events" :key="event.id">
							<td>{{ formatDate(event.created_at) }}</td>
							<td>
								<strong>{{ event.actor_email || 'Система / неизвестно' }}</strong>
								<div class="cp-muted audit-small">{{ event.actor_user_id || '—' }}</div>
							</td>
							<td><code class="cp-code">{{ event.action }}</code></td>
							<td>{{ event.target_type || '—' }}<div v-if="event.target_id" class="cp-muted audit-small">{{ event.target_id }}</div></td>
							<td><span class="cp-chip" :class="resultClass(event.result)">{{ resultLabel(event.result) }}</span></td>
							<td>{{ event.source }}</td>
							<td><code class="cp-code audit-request-id">{{ event.request_id || '—' }}</code></td>
							<td><BaseButton variant="ghost" size="small" text="Детали" :loading="detailLoading && selected?.id === event.id" @click="openEvent(event)" /></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div v-if="total" class="audit-pagination">
			<span class="cp-muted">{{ pageStart }}–{{ pageEnd }} из {{ total }}</span>
			<div class="cp-actions">
				<BaseButton variant="outline" size="small" text="Назад" :disabled="!hasPrevious" @click="previousPage" />
				<BaseButton variant="outline" size="small" text="Дальше" :disabled="!hasNext" @click="nextPage" />
			</div>
		</div>

		<article v-if="selected" class="cp-card audit-detail">
			<div class="audit-detail__head">
				<div>
					<p class="cp-eyebrow">Событие</p>
					<h3 class="audit-detail__title">{{ selected.action }}</h3>
				</div>
				<BaseButton variant="ghost" size="small" text="Закрыть" @click="selected = null" />
			</div>
			<div class="audit-detail__grid">
				<div><span>Время</span><strong>{{ formatDate(selected.created_at) }}</strong></div>
				<div><span>Пользователь</span><strong>{{ selected.actor_email || selected.actor_user_id || 'Система / неизвестно' }}</strong></div>
				<div><span>Роли</span><strong>{{ selected.actor_roles?.join(', ') || '—' }}</strong></div>
				<div><span>Результат</span><strong>{{ resultLabel(selected.result) }}</strong></div>
				<div><span>HTTP</span><strong>{{ selected.method || '—' }} {{ selected.path || '' }}</strong></div>
				<div><span>Request ID</span><strong>{{ selected.request_id || '—' }}</strong></div>
				<div><span>Объект</span><strong>{{ selected.target_type || '—' }} {{ selected.target_id || '' }}</strong></div>
				<div><span>Ошибка</span><strong>{{ selected.error_code || '—' }}</strong></div>
			</div>
			<div class="audit-evidence">
				<span>Client evidence</span>
				<code>IP: {{ selected.client_ip_hash || '—' }}</code>
				<code>UA: {{ selected.user_agent_hash || '—' }}</code>
			</div>
			<div>
				<span class="cp-muted">Безопасные metadata</span>
				<pre class="audit-json">{{ JSON.stringify(selected.metadata || {}, null, 2) }}</pre>
			</div>
		</article>
	</section>
</template>

<style scoped>
.audit-filters {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: 0.75rem;
	margin-bottom: 1rem;
}
.filter-input {
	min-height: 2.5rem;
	padding: 0.55rem 0.7rem;
	border: 1px solid var(--border-color);
	border-radius: 0.5rem;
	background: var(--medium-bg);
	color: var(--text-color);
}
.audit-filter-actions,
.audit-pagination,
.audit-detail__head,
.audit-evidence {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}
.audit-filter-actions { flex-wrap: wrap; }
.audit-pagination {
	justify-content: space-between;
	margin-top: 1rem;
}
.audit-small {
	font-size: 0.75rem;
	max-width: 250px;
	overflow-wrap: anywhere;
}
.audit-request-id {
	max-width: 180px;
	display: inline-block;
	overflow-wrap: anywhere;
}
.audit-detail {
	margin-top: 1rem;
}
.audit-detail__head {
	justify-content: space-between;
	margin-bottom: 1rem;
}
.audit-detail__title { margin: 0; }
.audit-detail__grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	gap: 0.8rem;
	margin-bottom: 1rem;
}
.audit-detail__grid div,
.audit-evidence {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 0.2rem;
}
.audit-detail__grid span,
.audit-evidence span { color: var(--muted-text-color, #94a3b8); font-size: 0.8rem; }
.audit-evidence { margin-bottom: 1rem; }
.audit-json {
	margin-top: 0.5rem;
	padding: 0.85rem;
	border: 1px solid var(--border-color);
	border-radius: 0.5rem;
	background: var(--dark-bg);
	white-space: pre-wrap;
	word-break: break-word;
	max-height: 320px;
	overflow: auto;
}
@media (max-width: 720px) {
	.audit-pagination { align-items: flex-start; flex-direction: column; }
}
</style>
