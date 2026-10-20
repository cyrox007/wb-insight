<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CP_Diagnostics from '@/API/ControlPanel/CP_Diagnostics'

const emit = defineEmits(['open'])

const filters = reactive({
	lookback_hours: 72,
	severity: '',
	domain: '',
	user_query: '',
	limit: 50,
})

const result = ref(null)
const isLoading = ref(false)
const loadError = ref('')

const items = computed(() => result.value?.items || [])
const summary = computed(() => result.value?.summary || {})
const total = computed(() => Number(result.value?.total || 0))
const offset = computed(() => Number(result.value?.offset || 0))
const limit = computed(() => Number(result.value?.limit || filters.limit || 50))
const hasMore = computed(() => Boolean(result.value?.has_more))
const canBack = computed(() => offset.value > 0)

function formatDate(value) {
	return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function safeJson(value) {
	return JSON.stringify(value || {}, null, 2)
}

function severityText(value) {
	return ({
		critical: 'Критическая',
		error: 'Ошибка',
		warning: 'Предупреждение',
		info: 'Информация',
	}[value] || value || '—')
}

function severityClass(value) {
	return {
		'cp-chip--inactive': ['critical', 'error'].includes(value),
		'cp-chip--warning': value === 'warning',
		'cp-chip--active': value === 'info',
	}
}

function sourceText(value) {
	return ({
		operation_log: 'Операционный журнал',
		payment_state: 'Состояние платежа',
		sync_job: 'Фоновая задача',
		sync_state: 'Состояние данных',
		credential_state: 'Подключение маркетплейса',
	}[value] || value || '—')
}

function requestParams(targetOffset = 0) {
	const params = {
		lookback_hours: Number(filters.lookback_hours || 72),
		limit: Number(filters.limit || 50),
		offset: Math.max(0, Number(targetOffset || 0)),
	}
	if (filters.severity) params.severity = filters.severity
	if (filters.domain) params.domain = filters.domain
	if (filters.user_query.trim()) params.user_query = filters.user_query.trim()
	return params
}

async function loadIncidents(targetOffset = 0) {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Diagnostics.getIncidents(requestParams(targetOffset))
		result.value = data
	} catch (error) {
		console.error('Ошибка загрузки очереди инцидентов:', error)
		result.value = null
		loadError.value = error.response?.data?.detail || error.response?.data?.error?.message || 'Не удалось загрузить очередь инцидентов.'
	} finally {
		isLoading.value = false
	}
}

function resetFilters() {
	filters.lookback_hours = 72
	filters.severity = ''
	filters.domain = ''
	filters.user_query = ''
	filters.limit = 50
	loadIncidents(0)
}

function previousPage() {
	if (!canBack.value) return
	loadIncidents(Math.max(0, offset.value - limit.value))
}

function nextPage() {
	if (!hasMore.value) return
	loadIncidents(offset.value + limit.value)
}

function openIncident(item) {
	emit('open', item?.diagnostics || {})
}

onMounted(() => loadIncidents(0))
</script>

<template>
	<section class="cp-card incident-center">
		<div class="incident-center__head">
			<div>
				<p class="cp-eyebrow">Требует внимания</p>
				<h3>Очередь операционных инцидентов</h3>
				<p class="cp-card-note">Система сама собирает сбои платежей, Wildberries, синхронизации и технических операций и ведёт в связанную трассировку.</p>
			</div>
			<BaseButton variant="secondary" size="small" text="Обновить" :loading="isLoading" @click="loadIncidents(offset)" />
		</div>

		<form class="incident-filters" @submit.prevent="loadIncidents(0)">
			<label class="cp-field-label">
				<span>Период</span>
				<select v-model.number="filters.lookback_hours">
					<option :value="24">24 часа</option>
					<option :value="72">3 дня</option>
					<option :value="168">7 дней</option>
					<option :value="720">30 дней</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Важность</span>
				<select v-model="filters.severity">
					<option value="">Все</option>
					<option value="critical">Критическая</option>
					<option value="error">Ошибка</option>
					<option value="warning">Предупреждение</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Подсистема</span>
				<select v-model="filters.domain">
					<option value="">Все</option>
					<option value="payment">Платежи</option>
					<option value="sync">Синхронизация</option>
					<option value="access">Доступ к маркетплейсу</option>
					<option value="external_api">Внешние API</option>
					<option value="mail">Почта</option>
					<option value="auth">Авторизация</option>
					<option value="dashboard">Дашборд</option>
					<option value="finance">Финансы</option>
					<option value="http">HTTP</option>
					<option value="system">Система</option>
				</select>
			</label>
			<label class="cp-field-label incident-filters__user">
				<span>Пользователь</span>
				<input v-model.trim="filters.user_query" type="search" autocomplete="off" placeholder="email, ФИО, UUID, телефон или ИНН">
			</label>
			<div class="incident-filters__actions">
				<BaseButton variant="primary" text="Применить" type="submit" />
				<BaseButton variant="secondary" text="Сбросить" type="button" @click="resetFilters" />
			</div>
		</form>

		<div v-if="loadError" class="cp-state cp-state--error" role="alert">{{ loadError }}</div>
		<div v-else-if="isLoading && !result" class="cp-state" role="status">Собираем проблемные операции и текущее состояние…</div>

		<template v-if="result">
			<div class="incident-summary" aria-label="Сводка инцидентов">
				<div><span>Всего</span><strong>{{ total }}</strong></div>
				<div><span>Критические</span><strong>{{ summary.critical || 0 }}</strong></div>
				<div><span>Ошибки</span><strong>{{ summary.error || 0 }}</strong></div>
				<div><span>Предупреждения</span><strong>{{ summary.warning || 0 }}</strong></div>
			</div>

			<p v-if="items.length === 0" class="cp-card-note incident-empty">По выбранным условиям проблем не найдено.</p>

			<div v-else class="incident-list">
				<article v-for="item in items" :key="item.id" class="incident-item">
					<div class="incident-item__main">
						<div class="incident-item__head">
							<div>
								<span class="cp-eyebrow">{{ item.domain }} · {{ sourceText(item.source) }}</span>
								<h4>{{ item.title }}</h4>
							</div>
							<span class="cp-chip" :class="severityClass(item.severity)">{{ severityText(item.severity) }}</span>
						</div>
						<div class="incident-meta">
							<span><strong>Код:</strong> <code>{{ item.code }}</code></span>
							<span><strong>Последнее событие:</strong> {{ formatDate(item.last_seen_at) }}</span>
							<span><strong>Повторов:</strong> {{ item.occurrences }}</span>
							<span v-if="item.user"><strong>Пользователь:</strong> {{ item.user.full_name || item.user.email }} · {{ item.user.email }}</span>
							<span v-else-if="item.user_id"><strong>Пользователь:</strong> <code>{{ item.user_id }}</code></span>
							<span v-if="item.subject_id"><strong>Объект:</strong> {{ item.subject_type || '—' }} · <code>{{ item.subject_id }}</code></span>
						</div>
						<details class="incident-details">
							<summary>Технические детали</summary>
							<pre>{{ safeJson(item.details) }}</pre>
						</details>
					</div>
					<BaseButton variant="outline" size="small" text="Открыть в диагностике" @click="openIncident(item)" />
				</article>
			</div>

			<div v-if="total" class="incident-pagination">
				<BaseButton variant="secondary" text="Назад" :disabled="!canBack || isLoading" @click="previousPage" />
				<span>{{ offset + 1 }}–{{ Math.min(offset + items.length, total) }} из {{ total }}</span>
				<BaseButton variant="secondary" text="Дальше" :disabled="!hasMore || isLoading" @click="nextPage" />
			</div>
		</template>
	</section>
</template>

<style scoped>
.incident-center { display: grid; gap: 1rem; }
.incident-center__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.incident-center__head h3 { margin: 0; }
.incident-filters { display: grid; grid-template-columns: 150px 160px 190px minmax(220px, 1fr) auto; gap: 0.65rem; align-items: end; }
.incident-filters__actions { display: flex; gap: 0.5rem; }
.incident-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.65rem; }
.incident-summary > div { display: grid; gap: 0.15rem; padding: 0.65rem; border: 1px solid var(--border-color); border-radius: 10px; background: var(--surface-soft); }
.incident-summary span { color: var(--text-muted); font-size: 0.82rem; }
.incident-summary strong { font-size: 1.3rem; }
.incident-list { display: grid; gap: 0.65rem; }
.incident-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 0.8rem; border: 1px solid var(--border-color); border-radius: 12px; background: var(--surface-soft); }
.incident-item__main { min-width: 0; flex: 1; }
.incident-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; }
.incident-item__head h4 { margin: 0.15rem 0 0; }
.incident-meta { display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; margin-top: 0.55rem; color: var(--text-muted); font-size: 0.84rem; }
.incident-meta code { overflow-wrap: anywhere; }
.incident-details { margin-top: 0.55rem; }
.incident-details summary { cursor: pointer; color: var(--text-muted); }
.incident-details pre { max-height: 260px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
.incident-pagination { display: flex; align-items: center; justify-content: center; gap: 0.75rem; }
.incident-empty { margin: 0; }
@media (max-width: 1100px) {
	.incident-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	.incident-filters__actions { grid-column: 1 / -1; justify-content: flex-end; }
}
@media (max-width: 720px) {
	.incident-center__head, .incident-item, .incident-item__head { flex-direction: column; align-items: stretch; }
	.incident-filters { grid-template-columns: 1fr; }
	.incident-filters__actions { grid-column: auto; flex-direction: column; }
	.incident-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	.incident-pagination { justify-content: space-between; }
}
</style>
