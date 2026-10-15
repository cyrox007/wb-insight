<script setup>
import { computed, ref } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CP_Diagnostics from '@/API/ControlPanel/CP_Diagnostics'
import UserDiagnostics from './index.vue'

const query = ref('')
const lookup = ref(null)
const trace = ref(null)
const isLoading = ref(false)
const loadError = ref('')

const matches = computed(() => lookup.value?.matches || [])
const contexts = computed(() => lookup.value?.user_contexts || [])
const lookupEvents = computed(() => lookup.value?.events || [])
const traceEvents = computed(() => trace.value?.events || [])
const visibleEvents = computed(() => traceEvents.value.length ? traceEvents.value : lookupEvents.value)

function formatDate(value) {
	return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function safeJson(value) {
	return JSON.stringify(value || {}, null, 2)
}

function statusClass(status) {
	return {
		'cp-chip--active': ['success', 'info'].includes(status),
		'cp-chip--warning': ['started', 'warning'].includes(status),
		'cp-chip--inactive': ['failed', 'critical', 'error'].includes(status),
	}
}

async function runSearch() {
	const value = query.value.trim()
	if (!value) {
		loadError.value = 'Введите email, UUID пользователя, операции, токена, платежа, тарифа, задачи или request_id.'
		return
	}

	isLoading.value = true
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
		isLoading.value = false
	}
}

async function loadOperation(operationId) {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Diagnostics.getOperation(operationId)
		trace.value = data
	} catch (error) {
		console.error('Ошибка загрузки цепочки операции:', error)
		loadError.value = error.response?.data?.detail || 'Не удалось восстановить цепочку операции.'
	} finally {
		isLoading.value = false
	}
}

async function loadRequest(requestId) {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Diagnostics.getRequest(requestId)
		trace.value = data
	} catch (error) {
		console.error('Ошибка загрузки HTTP-запроса:', error)
		loadError.value = error.response?.data?.detail || 'Не удалось восстановить HTTP-запрос.'
	} finally {
		isLoading.value = false
	}
}
</script>

<template>
	<section class="trace-hub">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Сквозная трассировка</p>
				<h2 class="cp-detail-title">Проводник операции</h2>
				<p class="cp-subtitle">Один поиск связывает пользователя, профиль, тариф, кабинет маркетплейса, HTTP-запрос, фоновые задачи, внешние API и итоговый ответ приложения.</p>
			</div>
		</header>

		<form class="cp-card trace-search" @submit.prevent="runSearch">
			<label class="cp-field-label trace-search__field">
				<span>Любой известный идентификатор</span>
				<input v-model.trim="query" type="search" autocomplete="off" placeholder="email, user_id, operation_id, request_id, token_id, payment_id, tariff_id, job_id">
			</label>
			<BaseButton variant="primary" text="Найти цепочку" :loading="isLoading" type="submit" />
		</form>

		<div v-if="loadError" class="cp-state cp-state--error" role="alert">{{ loadError }}</div>
		<div v-else-if="isLoading" class="cp-state" role="status">Восстанавливаем связи и шаги операции…</div>

		<template v-if="lookup && !isLoading">
			<section class="cp-card trace-summary">
				<div class="trace-summary__head">
					<div><p class="cp-eyebrow">Результат поиска</p><h3>{{ lookup.query }}</h3></div>
					<span class="cp-muted">совпадений: {{ matches.length }}</span>
				</div>
				<div v-if="matches.length" class="trace-matches">
					<div v-for="item in matches" :key="`${item.kind}-${item.id}`" class="trace-match">
						<strong>{{ item.kind }}</strong><span>{{ item.label || '—' }}</span><code>{{ item.id }}</code><small v-if="item.user_id">пользователь: {{ item.user_id }}</small>
					</div>
				</div>
				<p v-else class="cp-card-note">Прямое совпадение сущности не найдено. Ниже всё равно показаны события, если идентификатор встретился в трассировке.</p>
			</section>

			<section v-if="contexts.length" class="trace-contexts">
				<article v-for="context in contexts" :key="context.user?.id || context.user_id" class="cp-card trace-context">
					<div class="trace-context__head">
						<div><p class="cp-eyebrow">Контекст пользователя на текущий момент</p><h3>{{ context.user?.full_name || context.user?.email || context.user_id }}</h3></div>
						<span class="cp-chip" :class="context.user?.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">{{ context.user?.is_active ? 'Активен' : 'Недоступен' }}</span>
					</div>
					<div class="trace-context-grid">
						<div><span>Профиль</span><strong>{{ context.user?.entity_type || '—' }}</strong><small>{{ context.user?.email || '—' }} · {{ (context.user?.roles || []).join(', ') || 'user' }}</small></div>
						<div><span>Тариф</span><strong>{{ context.subscription?.tariff?.name || 'Нет активной подписки' }}</strong><small>{{ context.subscription?.status || '—' }} · до {{ formatDate(context.subscription?.period_end) }}</small></div>
						<div><span>Лимиты</span><pre>{{ safeJson(context.subscription?.tariff?.limits || {}) }}</pre></div>
						<div><span>Подключения маркетплейса</span><strong>{{ context.marketplace_credentials?.length || 0 }}</strong><small>{{ (context.marketplace_credentials || []).filter(item => item.is_valid).length }} доступно</small></div>
					</div>
					<details v-if="context.marketplace_credentials?.length" class="trace-details"><summary>Метаданные подключений</summary><pre>{{ safeJson(context.marketplace_credentials) }}</pre></details>
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

			<section class="cp-card">
				<div class="trace-summary__head">
					<div><p class="cp-eyebrow">Шаги обработки</p><h3>Временная шкала</h3></div>
					<span class="cp-muted">{{ visibleEvents.length }} событий</span>
				</div>
				<p v-if="trace?.root_operation_id" class="cp-card-note">Корневая операция: <code>{{ trace.root_operation_id }}</code> · связанных операций: {{ trace.operation_ids?.length || 0 }}</p>
				<div v-if="visibleEvents.length" class="trace-events">
					<details v-for="event in visibleEvents" :key="event.id" class="trace-event">
						<summary>
							<span class="trace-event__time">{{ formatDate(event.created_at) }}</span>
							<span class="trace-event__name"><strong>{{ event.component || event.domain }} · {{ event.step }}</strong><small>{{ event.message || event.operation }}</small></span>
							<span class="cp-chip" :class="statusClass(event.status)">{{ event.status }}</span>
						</summary>
						<div class="trace-event__body">
							<div class="trace-event-grid">
								<div><span>Последовательность</span><strong>#{{ event.sequence_no ?? '—' }} · {{ event.event_kind || '—' }} · {{ event.direction || '—' }}</strong></div>
								<div><span>HTTP / время</span><strong>{{ event.http_status || '—' }} · {{ event.duration_ms ?? '—' }} мс</strong></div>
								<div><span>Операция</span><code>{{ event.operation_id }}</code></div>
								<div><span>Родитель</span><code>{{ event.parent_operation_id || '—' }}</code></div>
								<div><span>Запрос</span><code>{{ event.request_id || '—' }}</code></div>
								<div><span>Субъект</span><code>{{ event.subject_type || '—' }} · {{ event.subject_id || '—' }}</code></div>
								<div><span>Провайдер</span><strong>{{ event.provider || '—' }}</strong></div>
								<div><span>Ошибка</span><strong>{{ event.error_code || '—' }}</strong></div>
							</div>
							<div class="trace-payloads">
								<div><span>Контекст</span><pre>{{ safeJson(event.context) }}</pre></div>
								<div><span>Вход</span><pre>{{ safeJson(event.input) }}</pre></div>
								<div><span>Выход</span><pre>{{ safeJson(event.output) }}</pre></div>
								<div><span>Метрики</span><pre>{{ safeJson(event.metrics) }}</pre></div>
							</div>
						</div>
					</details>
				</div>
			</section>
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
.trace-matches, .trace-contexts, .trace-events, .trace-links { display: grid; gap: 0.65rem; margin-top: 0.85rem; }
.trace-match { display: grid; grid-template-columns: minmax(120px, auto) 1fr; gap: 0.2rem 0.75rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.trace-match code, .trace-match small { grid-column: 2; overflow-wrap: anywhere; }
.trace-context-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.65rem; margin-top: 0.85rem; }
.trace-context-grid > div { display: grid; gap: 0.2rem; min-width: 0; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.trace-context-grid span, .trace-context-grid small { color: var(--text-muted); }
.trace-context-grid pre, .trace-details pre { margin: 0.3rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
.trace-details { margin-top: 0.75rem; }
.trace-details summary { cursor: pointer; }
.trace-link { width: 100%; display: grid; grid-template-columns: 120px 1fr; gap: 0.75rem; text-align: left; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; background: var(--surface-soft); cursor: pointer; }
.trace-link code { overflow-wrap: anywhere; }
.trace-event { border: 1px solid var(--border-color); border-radius: 12px; overflow: clip; }
.trace-event summary { cursor: pointer; display: flex; align-items: center; gap: 0.8rem; padding: 0.75rem; }
.trace-event__time { min-width: 145px; font-size: 0.8rem; color: var(--text-muted); }
.trace-event__name { display: grid; flex: 1; gap: 0.1rem; }
.trace-event__name small { color: var(--text-muted); }
.trace-event__body { border-top: 1px solid var(--border-color); padding: 0.8rem; }
.trace-event-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; }
.trace-event-grid > div { display: grid; gap: 0.2rem; min-width: 0; }
.trace-event-grid span, .trace-payloads span { color: var(--text-muted); }
.trace-event-grid code { overflow-wrap: anywhere; }
.trace-payloads { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; margin-top: 0.8rem; }
.trace-payloads > div { min-width: 0; }
.trace-payloads pre { margin: 0.3rem 0 0; max-height: 360px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
.trace-user-diagnostics { border-top: 1px solid var(--border-color); padding-top: 1rem; }
@media (max-width: 1000px) { .trace-context-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) {
	.trace-search, .trace-summary__head, .trace-context__head, .trace-event summary { align-items: stretch; flex-direction: column; }
	.trace-context-grid, .trace-event-grid, .trace-payloads { grid-template-columns: 1fr; }
	.trace-match, .trace-link { grid-template-columns: 1fr; }
	.trace-match code, .trace-match small { grid-column: auto; }
	.trace-event__time { min-width: 0; }
}
</style>
