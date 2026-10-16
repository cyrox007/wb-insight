<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CP_Diagnostics from '@/API/ControlPanel/CP_Diagnostics'
import EventTimeline from './EventTimeline.vue'
import FilterPanel from './FilterPanel.vue'
import UserDiagnostics from './index.vue'

const route = useRoute()
const router = useRouter()
const query = ref('')
const lookup = ref(null)
const trace = ref(null)
const filteredResult = ref(null)
const lastFilterParams = ref({})
const filterPanel = ref(null)
const isLookupLoading = ref(false)
const isFilterLoading = ref(false)
const loadError = ref('')
let routeSyncInProgress = false

const FILTER_QUERY_KEYS = new Set([
	'user_query', 'token_query', 'payment_query', 'tariff_query', 'job_query',
	'operation_id', 'request_id', 'domain', 'operation', 'status', 'severity',
	'component', 'event_kind', 'direction', 'provider', 'http_statuses',
	'http_status_group', 'error_code', 'min_duration_ms', 'created_from',
	'created_to', 'attention_only', 'unfinished_only', 'retry_only', 'limit',
])

const matches = computed(() => lookup.value?.matches || [])
const contexts = computed(() => lookup.value?.user_contexts || [])
const lookupEvents = computed(() => lookup.value?.events || [])
const traceEvents = computed(() => trace.value?.events || [])
const filteredEvents = computed(() => filteredResult.value?.items || [])
const filterTotal = computed(() => Number(filteredResult.value?.total || 0))
const filterOffset = computed(() => Number(filteredResult.value?.offset || 0))
const filterLimit = computed(() => Number(filteredResult.value?.limit || 100))
const canFilterBack = computed(() => filterOffset.value > 0)
const canFilterForward = computed(() => Boolean(filteredResult.value?.has_more))

function formatDate(value) {
	return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function safeJson(value) {
	return JSON.stringify(value || {}, null, 2)
}

function firstQueryValue(value) {
	return Array.isArray(value) ? value[0] : value
}

function filtersFromRoute() {
	const params = {}
	for (const [key, rawValue] of Object.entries(route.query || {})) {
		if (!FILTER_QUERY_KEYS.has(key)) continue
		const value = firstQueryValue(rawValue)
		if (value !== undefined && value !== null && String(value).trim() !== '') {
			params[key] = value
		}
	}
	return params
}

function offsetFromRoute() {
	const value = Number(firstQueryValue(route.query?.offset) || 0)
	return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0
}

function routeQueryForFilters(params, offset) {
	const result = {}
	for (const [key, value] of Object.entries(params || {})) {
		if (!FILTER_QUERY_KEYS.has(key) || value === undefined || value === null || value === '' || value === false) continue
		result[key] = value === true ? '1' : String(value)
	}
	if (offset > 0) result.offset = String(offset)
	return result
}

async function syncFilterRoute(params, offset) {
	routeSyncInProgress = true
	try {
		await router.replace({
			name: 'control-panel.diagnostics',
			query: routeQueryForFilters(params, offset),
		})
	} finally {
		await nextTick()
		routeSyncInProgress = false
	}
}

async function runSearch() {
	const value = query.value.trim()
	if (!value) {
		loadError.value = 'Введите email, UUID пользователя, операции, токена, платежа, тарифа, задачи или request_id.'
		return
	}

	isLookupLoading.value = true
	loadError.value = ''
	trace.value = null
	try {
		const { data } = await CP_Diagnostics.search(value, 150)
		lookup.value = data
	} catch (error) {
		console.error('Ошибка сквозного диагностического поиска:', error)
		lookup.value = null
		loadError.value = error.response?.data?.detail || error.response?.data?.error?.message || 'Не удалось выполнить диагностический поиск.'
	} finally {
		isLookupLoading.value = false
	}
}

async function loadOperation(operationId) {
	if (!operationId) return
	isLookupLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Diagnostics.getOperation(operationId)
		trace.value = data
	} catch (error) {
		console.error('Ошибка загрузки цепочки операции:', error)
		loadError.value = error.response?.data?.detail || 'Не удалось восстановить цепочку операции.'
	} finally {
		isLookupLoading.value = false
	}
}

async function loadRequest(requestId) {
	if (!requestId) return
	isLookupLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Diagnostics.getRequest(requestId)
		trace.value = data
	} catch (error) {
		console.error('Ошибка загрузки HTTP-запроса:', error)
		loadError.value = error.response?.data?.detail || 'Не удалось восстановить HTTP-запрос.'
	} finally {
		isLookupLoading.value = false
	}
}

async function loadFiltered(params, offset = 0, { syncRoute = true } = {}) {
	isFilterLoading.value = true
	loadError.value = ''
	lastFilterParams.value = { ...params }
	try {
		const { data } = await CP_Diagnostics.getEvents({
			...params,
			offset,
		})
		filteredResult.value = data
		if (syncRoute) await syncFilterRoute(params, offset)
	} catch (error) {
		console.error('Ошибка фильтрации диагностического журнала:', error)
		filteredResult.value = null
		loadError.value = error.response?.data?.detail || error.response?.data?.error?.message || 'Не удалось применить фильтры журнала.'
	} finally {
		isFilterLoading.value = false
	}
}

async function resetFiltered() {
	filteredResult.value = null
	lastFilterParams.value = {}
	await syncFilterRoute({}, 0)
}

function applyMatchAsFilter(item) {
	filterPanel.value?.applyMatch(item)
}

function filterCredential(credential) {
	if (!credential?.id) return
	filterPanel.value?.setFilters({ token_query: credential.id })
}

function filterContextUser(context) {
	const userId = context?.user?.id || context?.user_id
	if (!userId) return
	filterPanel.value?.setFilters({ user_query: userId })
}

function filterContextTariff(context) {
	const tariffId = context?.subscription?.tariff?.id
	if (!tariffId) return
	filterPanel.value?.setFilters({ tariff_query: tariffId })
}

function previousFilterPage() {
	if (!canFilterBack.value) return
	loadFiltered(lastFilterParams.value, Math.max(0, filterOffset.value - filterLimit.value))
}

function nextFilterPage() {
	if (!canFilterForward.value) return
	loadFiltered(lastFilterParams.value, filterOffset.value + filterLimit.value)
}

async function applyRouteFilters() {
	const params = filtersFromRoute()
	const offset = offsetFromRoute()
	if (!Object.keys(params).length && offset === 0) return
	await nextTick()
	filterPanel.value?.setFilters(params, { apply: false })
	await loadFiltered(params, offset, { syncRoute: false })
}

onMounted(applyRouteFilters)
watch(
	() => route.fullPath,
	() => {
		if (!routeSyncInProgress) applyRouteFilters()
	},
)
</script>

<template>
	<section class="trace-hub">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Сквозная трассировка</p>
				<h2 class="cp-detail-title">Проводник операции</h2>
				<p class="cp-subtitle">Поиск и комбинируемые фильтры связывают пользователя, тариф, кабинет маркетплейса, платёж, HTTP-запрос, фоновые задачи, внешние API и итоговый ответ приложения.</p>
			</div>
		</header>

		<form class="cp-card trace-search" @submit.prevent="runSearch">
			<label class="cp-field-label trace-search__field">
				<span>Быстрый сквозной поиск</span>
				<input v-model.trim="query" type="search" autocomplete="off" placeholder="email, user_id, operation_id, request_id, token_id, payment_id, tariff_id, job_id">
			</label>
			<BaseButton variant="primary" text="Найти цепочку" :loading="isLookupLoading" type="submit" />
		</form>

		<div v-if="loadError" class="cp-state cp-state--error" role="alert">{{ loadError }}</div>
		<div v-else-if="isLookupLoading" class="cp-state" role="status">Восстанавливаем связи и шаги операции…</div>

		<template v-if="lookup && !isLookupLoading">
			<section class="cp-card trace-summary">
				<div class="trace-summary__head">
					<div><p class="cp-eyebrow">Результат поиска</p><h3>{{ lookup.query }}</h3></div>
					<span class="cp-muted">совпадений: {{ matches.length }}</span>
				</div>
				<div v-if="matches.length" class="trace-matches">
					<div v-for="item in matches" :key="`${item.kind}-${item.id}`" class="trace-match">
						<div class="trace-match__content">
							<strong>{{ item.kind }}</strong>
							<span>{{ item.label || '—' }}</span>
							<code>{{ item.id }}</code>
							<small v-if="item.user_id">пользователь: {{ item.user_id }}</small>
						</div>
						<button type="button" class="trace-match__filter" @click="applyMatchAsFilter(item)">Показать журнал</button>
					</div>
				</div>
				<p v-else class="cp-card-note">Прямое совпадение сущности не найдено. Ниже всё равно показаны события, если идентификатор встретился в трассировке.</p>
			</section>

			<section v-if="contexts.length" class="trace-contexts">
				<article v-for="context in contexts" :key="context.user?.id || context.user_id" class="cp-card trace-context">
					<div class="trace-context__head">
						<div><p class="cp-eyebrow">Контекст пользователя на текущий момент</p><h3>{{ context.user?.full_name || context.user?.email || context.user_id }}</h3></div>
						<div class="trace-context__actions">
							<span class="cp-chip" :class="context.user?.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">{{ context.user?.is_active ? 'Активен' : 'Недоступен' }}</span>
							<button type="button" class="trace-context__filter" @click="filterContextUser(context)">Журнал пользователя</button>
						</div>
					</div>
					<div class="trace-context-grid">
						<div><span>Профиль</span><strong>{{ context.user?.entity_type || '—' }}</strong><small>{{ context.user?.email || '—' }} · {{ (context.user?.roles || []).join(', ') || 'user' }}</small></div>
						<div><span>Тариф</span><strong>{{ context.subscription?.tariff?.name || 'Нет активной подписки' }}</strong><small>{{ context.subscription?.status || '—' }} · до {{ formatDate(context.subscription?.period_end) }}</small><button v-if="context.subscription?.tariff?.id" type="button" class="trace-inline-filter" @click="filterContextTariff(context)">Показать журнал тарифа</button></div>
						<div><span>Лимиты</span><pre>{{ safeJson(context.subscription?.tariff?.limits || {}) }}</pre></div>
						<div><span>Подключения маркетплейса</span><strong>{{ context.marketplace_credentials?.length || 0 }}</strong><small>{{ (context.marketplace_credentials || []).filter(item => item.is_valid).length }} доступно</small></div>
					</div>

					<div v-if="context.marketplace_credentials?.length" class="trace-credentials">
						<div v-for="credential in context.marketplace_credentials" :key="credential.id" class="trace-credential">
							<div>
								<strong>{{ credential.label || credential.external_account_id || credential.marketplace }}</strong>
								<code>{{ credential.id }}</code>
								<small>{{ credential.marketplace }} · {{ credential.token_type || 'token' }} · {{ credential.is_valid ? 'доступен' : 'проблема доступа' }}</small>
							</div>
							<button type="button" class="trace-context__filter" @click="filterCredential(credential)">Журнал кабинета</button>
						</div>
					</div>
				</article>
			</section>

			<section class="cp-card">
				<div class="trace-summary__head"><div><p class="cp-eyebrow">Корреляция</p><h3>Найденные цепочки</h3></div></div>
				<div class="trace-links">
					<button v-for="operationId in lookup.operation_ids || []" :key="operationId" type="button" class="trace-link" @click="loadOperation(operationId)"><span>operation_id</span><code>{{ operationId }}</code></button>
					<button v-for="requestId in lookup.request_ids || []" :key="requestId" type="button" class="trace-link" @click="loadRequest(requestId)"><span>request_id</span><code>{{ requestId }}</code></button>
				</div>
				<p v-if="!(lookup.operation_ids?.length || lookup.request_ids?.length)" class="cp-card-note">Для этого идентификатора трассируемых операций пока нет.</p>
			</section>

			<EventTimeline
				v-if="lookupEvents.length && !trace"
				:events="lookupEvents"
				title="События быстрого поиска"
				subtitle="Это последние события найденных сущностей. Для точной выборки используйте фильтры ниже."
				@open-operation="loadOperation"
				@open-request="loadRequest"
			/>
		</template>

		<EventTimeline
			v-if="trace"
			:events="traceEvents"
			title="Полная связанная цепочка"
			:subtitle="trace.root_operation_id ? `Корневая операция: ${trace.root_operation_id}` : `HTTP-запрос: ${trace.request_id || '—'}`"
			@open-operation="loadOperation"
			@open-request="loadRequest"
		/>

		<FilterPanel ref="filterPanel" @apply="loadFiltered" @reset="resetFiltered" />

		<template v-if="filteredResult">
			<div v-if="Object.keys(filteredResult.resolved || {}).length" class="cp-card resolved-filter-scope">
				<p class="cp-eyebrow">Разрешённые сущности</p>
				<pre>{{ safeJson(filteredResult.resolved) }}</pre>
			</div>

			<EventTimeline
				:events="filteredEvents"
				:total="filterTotal"
				:loading="isFilterLoading"
				title="Отфильтрованный журнал"
				:subtitle="filterTotal ? `Показано ${filterOffset + 1}–${Math.min(filterOffset + filteredEvents.length, filterTotal)} из ${filterTotal}` : 'По выбранным условиям событий нет'"
				@open-operation="loadOperation"
				@open-request="loadRequest"
			/>

			<div v-if="filterTotal" class="filter-pagination">
				<BaseButton variant="secondary" text="Назад" :disabled="!canFilterBack || isFilterLoading" @click="previousFilterPage" />
				<span>Страница {{ Math.floor(filterOffset / filterLimit) + 1 }}</span>
				<BaseButton variant="secondary" text="Дальше" :disabled="!canFilterForward || isFilterLoading" @click="nextFilterPage" />
			</div>
		</template>

		<section class="trace-user-diagnostics">
			<UserDiagnostics />
		</section>
	</section>
</template>

<style scoped>
.trace-hub { display: grid; gap: 1rem; }
.trace-search { display: flex; align-items: end; gap: 0.75rem; }
.trace-search__field { flex: 1; min-width: 0; }
.trace-summary__head, .trace-context__head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.trace-summary__head h3, .trace-context__head h3 { margin: 0; }
.trace-matches, .trace-contexts, .trace-links, .trace-credentials { display: grid; gap: 0.65rem; margin-top: 0.85rem; }
.trace-match { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.trace-match__content { display: grid; grid-template-columns: minmax(120px, auto) 1fr; gap: 0.2rem 0.75rem; min-width: 0; flex: 1; }
.trace-match__content code, .trace-match__content small { grid-column: 2; overflow-wrap: anywhere; }
.trace-match__filter, .trace-context__filter, .trace-inline-filter { flex: 0 0 auto; border: 1px solid var(--border-color); border-radius: 8px; background: var(--surface-soft); color: var(--text-color); padding: 0.45rem 0.65rem; cursor: pointer; }
.trace-inline-filter { width: fit-content; margin-top: 0.35rem; padding: 0.3rem 0.5rem; font-size: 0.78rem; }
.trace-context__actions { display: flex; align-items: center; gap: 0.5rem; }
.trace-context-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.65rem; margin-top: 0.85rem; }
.trace-context-grid > div { display: grid; gap: 0.2rem; min-width: 0; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.trace-context-grid span, .trace-context-grid small { color: var(--text-muted); }
.trace-context-grid pre, .resolved-filter-scope pre { margin: 0.3rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
.trace-credential { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.trace-credential > div { display: grid; gap: 0.15rem; min-width: 0; }
.trace-credential code { overflow-wrap: anywhere; }
.trace-credential small { color: var(--text-muted); }
.trace-link { width: 100%; display: grid; grid-template-columns: 120px 1fr; gap: 0.75rem; text-align: left; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; background: var(--surface-soft); color: var(--text-color); cursor: pointer; }
.trace-link code { overflow-wrap: anywhere; }
.filter-pagination { display: flex; align-items: center; justify-content: center; gap: 0.8rem; }
@media (max-width: 900px) { .trace-context-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) {
	.trace-search, .trace-match, .trace-summary__head, .trace-context__head, .trace-context__actions, .trace-credential { align-items: stretch; flex-direction: column; }
	.trace-context-grid { grid-template-columns: 1fr; }
	.trace-match__content { grid-template-columns: 1fr; }
	.trace-match__content code, .trace-match__content small { grid-column: 1; }
	.filter-pagination { justify-content: space-between; }
}
</style>
