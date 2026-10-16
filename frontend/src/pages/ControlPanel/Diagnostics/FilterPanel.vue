<script setup>
import { computed, reactive } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const emit = defineEmits(['apply', 'reset'])

const defaults = () => ({
	user_query: '',
	token_query: '',
	payment_query: '',
	tariff_query: '',
	job_query: '',
	operation_id: '',
	request_id: '',
	domain: '',
	operation: '',
	status: '',
	severity: '',
	component: '',
	event_kind: '',
	direction: '',
	provider: '',
	http_statuses: '',
	http_status_group: '',
	error_code: '',
	min_duration_ms: '',
	created_from: '',
	created_to: '',
	attention_only: false,
	unfinished_only: false,
	retry_only: false,
	limit: 100,
})

const filters = reactive(defaults())

const presets = [
	{ key: 'attention', label: 'Требует внимания' },
	{ key: 'payments', label: 'Ошибки платежей' },
	{ key: 'wb', label: 'Проблемы WB' },
	{ key: 'auth', label: '401 / 403' },
	{ key: 'rate-limit', label: '429' },
	{ key: 'server-errors', label: '5xx' },
	{ key: 'slow', label: 'Медленнее 5 сек.' },
	{ key: 'unfinished', label: 'Незавершённые' },
	{ key: 'retry', label: 'Повторные попытки' },
]

const activeCount = computed(() => {
	return Object.entries(filters).filter(([key, value]) => {
		if (key === 'limit') return value !== 100
		if (typeof value === 'boolean') return value
		return String(value ?? '').trim() !== ''
	}).length
})

function toIso(value) {
	if (!value) return undefined
	const date = new Date(value)
	return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

function toLocalDateTime(value) {
	if (!value) return ''
	const date = new Date(value)
	if (Number.isNaN(date.getTime())) return ''
	const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
	return local.toISOString().slice(0, 16)
}

function toBoolean(value) {
	return value === true || value === 'true' || value === '1' || value === 1
}

function payload() {
	const result = {}
	for (const [key, value] of Object.entries(filters)) {
		if (key === 'created_from' || key === 'created_to') continue
		if (typeof value === 'boolean') {
			if (value) result[key] = true
			continue
		}
		if (String(value ?? '').trim() !== '') result[key] = value
	}

	const createdFrom = toIso(filters.created_from)
	const createdTo = toIso(filters.created_to)
	if (createdFrom) result.created_from = createdFrom
	if (createdTo) result.created_to = createdTo
	return result
}

function applyFilters() {
	emit('apply', payload())
}

function resetFilters({ notify = true } = {}) {
	Object.assign(filters, defaults())
	if (notify) emit('reset')
}

function setFilters(values, { apply = true } = {}) {
	resetFilters({ notify: false })
	const booleanKeys = new Set(['attention_only', 'unfinished_only', 'retry_only'])
	for (const [key, rawValue] of Object.entries(values || {})) {
		if (!(key in filters) || rawValue === undefined || rawValue === null) continue
		if (booleanKeys.has(key)) {
			filters[key] = toBoolean(rawValue)
			continue
		}
		if (key === 'limit') {
			const parsed = Number(rawValue)
			filters.limit = [50, 100, 200, 500].includes(parsed) ? parsed : 100
			continue
		}
		if (key === 'created_from' || key === 'created_to') {
			filters[key] = toLocalDateTime(rawValue)
			continue
		}
		filters[key] = String(rawValue)
	}
	if (apply) applyFilters()
}

function applyPreset(key) {
	resetFilters({ notify: false })

	const handlers = {
		attention: () => { filters.attention_only = true },
		payments: () => {
			filters.domain = 'payment'
			filters.attention_only = true
		},
		wb: () => {
			filters.provider = 'wildberries'
			filters.attention_only = true
		},
		auth: () => { filters.http_statuses = '401,403' },
		'rate-limit': () => { filters.http_statuses = '429' },
		'server-errors': () => { filters.http_status_group = '5xx' },
		slow: () => { filters.min_duration_ms = 5000 },
		unfinished: () => { filters.unfinished_only = true },
		retry: () => { filters.retry_only = true },
	}

	handlers[key]?.()
	applyFilters()
}

function applyMatch(item) {
	if (!item) return
	resetFilters({ notify: false })

	const handlers = {
		user: () => { filters.user_query = item.id },
		marketplace_credential: () => { filters.token_query = item.id },
		payment: () => { filters.payment_query = item.id },
		sync_job: () => { filters.job_query = item.id },
		tariff: () => { filters.tariff_query = item.id },
		subscription: () => { filters.user_query = item.user_id || '' },
	}

	handlers[item.kind]?.()
	applyFilters()
}

defineExpose({ applyMatch, resetFilters, setFilters })
</script>

<template>
	<section class="cp-card diagnostic-filters">
		<div class="diagnostic-filters__head">
			<div>
				<p class="cp-eyebrow">Фильтры журнала</p>
				<h3>Отберите только нужную цепочку</h3>
				<p class="cp-card-note">Фильтры выполняются на сервере и комбинируются между собой.</p>
			</div>
			<span class="cp-chip" :class="activeCount ? 'cp-chip--active' : ''">Активно: {{ activeCount }}</span>
		</div>

		<div class="diagnostic-presets" aria-label="Быстрые фильтры">
			<button v-for="preset in presets" :key="preset.key" type="button" class="diagnostic-preset" @click="applyPreset(preset.key)">
				{{ preset.label }}
			</button>
		</div>

		<form class="diagnostic-filter-grid" @submit.prevent="applyFilters">
			<label class="cp-field-label">
				<span>Пользователь</span>
				<input v-model.trim="filters.user_query" type="search" autocomplete="off" placeholder="email, ФИО, UUID, телефон или ИНН">
			</label>
			<label class="cp-field-label">
				<span>Токен / кабинет</span>
				<input v-model.trim="filters.token_query" type="search" autocomplete="off" placeholder="UUID, метка или ID кабинета">
			</label>
			<label class="cp-field-label">
				<span>Платёж</span>
				<input v-model.trim="filters.payment_query" type="search" autocomplete="off" placeholder="payment_id или ID провайдера">
			</label>
			<label class="cp-field-label">
				<span>Тариф</span>
				<input v-model.trim="filters.tariff_query" type="search" autocomplete="off" placeholder="код, название или UUID">
			</label>
			<label class="cp-field-label">
				<span>Задача синхронизации</span>
				<input v-model.trim="filters.job_query" type="search" autocomplete="off" placeholder="job UUID или сущность">
			</label>
			<label class="cp-field-label">
				<span>operation_id</span>
				<input v-model.trim="filters.operation_id" type="text" autocomplete="off" placeholder="UUID операции">
			</label>
			<label class="cp-field-label">
				<span>request_id</span>
				<input v-model.trim="filters.request_id" type="text" autocomplete="off" placeholder="ID HTTP-запроса">
			</label>
			<label class="cp-field-label">
				<span>Подсистема</span>
				<select v-model="filters.domain">
					<option value="">Все</option>
					<option value="payment">Платежи</option>
					<option value="sync">Синхронизация</option>
					<option value="external_api">Внешние API</option>
					<option value="access">Доступ к маркетплейсу</option>
					<option value="auth">Авторизация</option>
					<option value="dashboard">Дашборд</option>
					<option value="finance">Финансы</option>
					<option value="mail">Почта</option>
					<option value="http">HTTP</option>
					<option value="system">Система</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Провайдер</span>
				<select v-model="filters.provider">
					<option value="">Все</option>
					<option value="wildberries">Wildberries</option>
					<option value="sber">Сбер</option>
					<option value="rusender">RuSender</option>
					<option value="resend">Resend</option>
					<option value="smtp">SMTP</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Статус</span>
				<select v-model="filters.status">
					<option value="">Все</option>
					<option value="started">Начато</option>
					<option value="success">Успешно</option>
					<option value="warning">Предупреждение</option>
					<option value="failed">Ошибка</option>
					<option value="info">Информация</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Важность</span>
				<select v-model="filters.severity">
					<option value="">Все</option>
					<option value="info">Информация</option>
					<option value="warning">Предупреждение</option>
					<option value="error">Ошибка</option>
					<option value="critical">Критическая</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Направление</span>
				<select v-model="filters.direction">
					<option value="">Все</option>
					<option value="incoming">Входящее</option>
					<option value="internal">Внутреннее</option>
					<option value="outgoing">Исходящее</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Тип события</span>
				<input v-model.trim="filters.event_kind" type="text" placeholder="external_http, sync_stage…">
			</label>
			<label class="cp-field-label">
				<span>Компонент</span>
				<input v-model.trim="filters.component" type="text" placeholder="sync.orders, authorization…">
			</label>
			<label class="cp-field-label">
				<span>Операция</span>
				<input v-model.trim="filters.operation" type="text" placeholder="marketplace_sync…">
			</label>
			<label class="cp-field-label">
				<span>HTTP-коды</span>
				<input v-model.trim="filters.http_statuses" type="text" inputmode="numeric" placeholder="401,403,429">
			</label>
			<label class="cp-field-label">
				<span>Группа HTTP</span>
				<select v-model="filters.http_status_group">
					<option value="">Все</option>
					<option value="2xx">2xx</option>
					<option value="3xx">3xx</option>
					<option value="4xx">4xx</option>
					<option value="5xx">5xx</option>
					<option value="errors">Все 4xx/5xx</option>
				</select>
			</label>
			<label class="cp-field-label">
				<span>Код ошибки</span>
				<input v-model.trim="filters.error_code" type="text" placeholder="WB_PERMISSION_DENIED">
			</label>
			<label class="cp-field-label">
				<span>Минимальная длительность, мс</span>
				<input v-model.number="filters.min_duration_ms" type="number" min="0" max="3600000" step="100" placeholder="5000">
			</label>
			<label class="cp-field-label">
				<span>Период с</span>
				<input v-model="filters.created_from" type="datetime-local">
			</label>
			<label class="cp-field-label">
				<span>Период по</span>
				<input v-model="filters.created_to" type="datetime-local">
			</label>
			<label class="cp-field-label">
				<span>Строк на странице</span>
				<select v-model.number="filters.limit">
					<option :value="50">50</option>
					<option :value="100">100</option>
					<option :value="200">200</option>
					<option :value="500">500</option>
				</select>
			</label>

			<div class="diagnostic-filter-toggles">
				<label><input v-model="filters.attention_only" type="checkbox"> Только требует внимания</label>
				<label><input v-model="filters.unfinished_only" type="checkbox"> Только незавершённые операции</label>
				<label><input v-model="filters.retry_only" type="checkbox"> Только повторные попытки</label>
			</div>

			<div class="diagnostic-filter-actions">
				<BaseButton variant="primary" text="Применить фильтры" type="submit" />
				<BaseButton variant="secondary" text="Сбросить" type="button" @click="resetFilters()" />
			</div>
		</form>
	</section>
</template>

<style scoped>
.diagnostic-filters { display: grid; gap: 1rem; }
.diagnostic-filters__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.diagnostic-filters__head h3 { margin: 0; }
.diagnostic-presets { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.diagnostic-preset { border: 1px solid var(--border-color); border-radius: 999px; background: var(--surface-soft); color: var(--text-color); padding: 0.45rem 0.75rem; cursor: pointer; }
.diagnostic-preset:hover { border-color: var(--primary-color); }
.diagnostic-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }
.diagnostic-filter-toggles { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 0.85rem 1.25rem; }
.diagnostic-filter-toggles label { display: inline-flex; align-items: center; gap: 0.4rem; cursor: pointer; }
.diagnostic-filter-actions { grid-column: 1 / -1; display: flex; gap: 0.65rem; justify-content: flex-end; }
@media (max-width: 1180px) { .diagnostic-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
	.diagnostic-filters__head { align-items: stretch; flex-direction: column; }
	.diagnostic-filter-grid { grid-template-columns: 1fr; }
	.diagnostic-filter-actions { justify-content: stretch; flex-direction: column; }
}
</style>
