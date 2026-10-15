<script setup>
import { computed, ref } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CP_Diagnostics from '@/API/ControlPanel/CP_Diagnostics'

const searchValue = ref('')
const diagnostics = ref(null)
const isLoading = ref(false)
const loadError = ref('')

const summary = computed(() => diagnostics.value?.summary || {})
const anomalies = computed(() => diagnostics.value?.anomalies || [])
const credentials = computed(() => diagnostics.value?.credentials || [])
const syncStates = computed(() => diagnostics.value?.sync_states || [])
const syncJobs = computed(() => diagnostics.value?.sync_jobs || [])
const payments = computed(() => diagnostics.value?.payments || [])
const calculation = computed(() => diagnostics.value?.calculation || {})
const timeline = computed(() => diagnostics.value?.operation_timeline || [])

function formatDate(value) {
	return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function formatMoney(value) {
	return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value || 0)) + ' ₽'
}

function statusText(value) {
	return ({
		started: 'Выполняется',
		success: 'Успешно',
		warning: 'Предупреждение',
		failed: 'Ошибка',
		info: 'Информация',
		pending: 'Ожидает',
		processing: 'Выполняется',
		done: 'Завершено',
		succeeded: 'Оплачено',
		cancelled: 'Отменено',
		ok: 'Рассчитано',
		empty: 'Нет данных',
		not_available: 'Недоступно',
		error: 'Ошибка',
	}[value] || value || '—')
}

function chipClass(value) {
	return {
		'cp-chip--active': ['success', 'done', 'succeeded', 'info', 'ok'].includes(value),
		'cp-chip--warning': ['warning', 'pending', 'processing', 'empty', 'not_available'].includes(value),
		'cp-chip--inactive': ['failed', 'cancelled', 'error', 'critical'].includes(value),
	}
}

function severityClass(value) {
	return {
		'diagnostic-anomaly--critical': value === 'critical',
		'diagnostic-anomaly--error': value === 'error',
		'diagnostic-anomaly--warning': value === 'warning',
	}
}

function isUuid(value) {
	return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

async function loadDiagnostics() {
	const query = searchValue.value.trim()
	if (!query) {
		loadError.value = 'Введите email или UUID пользователя.'
		return
	}
	isLoading.value = true
	loadError.value = ''
	try {
		const params = isUuid(query) ? { user_id: query } : { email: query }
		const { data } = await CP_Diagnostics.findUser(params)
		diagnostics.value = data
	} catch (error) {
		console.error('Ошибка загрузки диагностики:', error)
		diagnostics.value = null
		loadError.value = error.response?.data?.detail || error.response?.data?.error?.message || 'Не удалось получить диагностику пользователя.'
	} finally {
		isLoading.value = false
	}
}

function safeJson(value) {
	return JSON.stringify(value || {}, null, 2)
}
</script>

<template>
	<section class="cp-page diagnostics-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Поддержка и расследования</p>
				<h2 class="cp-detail-title">Диагностика пользователя</h2>
				<p class="cp-subtitle">Платежи, подключение Wildberries, полнота синхронизации, расчёты и техническая временная шкала в одном месте.</p>
			</div>
		</header>

		<form class="cp-card diagnostic-search" @submit.prevent="loadDiagnostics">
			<label class="cp-field-label diagnostic-search__field">
				<span>Email или UUID пользователя</span>
				<input v-model.trim="searchValue" type="search" autocomplete="off" placeholder="seller@example.ru или UUID">
			</label>
			<BaseButton variant="primary" text="Проверить" :loading="isLoading" type="submit" />
		</form>

		<div v-if="loadError" class="cp-state cp-state--error" role="alert">{{ loadError }}</div>
		<div v-else-if="isLoading" class="cp-state" role="status">Собираем состояние платежей, кабинетов, синхронизации и расчётов…</div>

		<template v-if="diagnostics && !isLoading">
			<section class="cp-card diagnostic-user">
				<div>
					<p class="cp-eyebrow">Пользователь</p>
					<h3>{{ diagnostics.user.full_name }}</h3>
					<p class="cp-card-note">{{ diagnostics.user.email }} · {{ diagnostics.user.id }}</p>
				</div>
				<span class="cp-chip" :class="diagnostics.user.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">{{ diagnostics.user.is_active ? 'Активен' : 'Деактивирован' }}</span>
			</section>

			<section class="diagnostic-summary" aria-label="Сводка диагностики">
				<article class="cp-card cp-metric-card"><span class="cp-metric-card__label">Проблемы</span><strong class="cp-metric-card__value">{{ summary.anomalies || 0 }}</strong><p class="cp-metric-card__hint">Критичных: {{ summary.critical || 0 }}</p></article>
				<article class="cp-card cp-metric-card"><span class="cp-metric-card__label">Подключения WB</span><strong class="cp-metric-card__value">{{ summary.valid_credentials || 0 }}/{{ summary.credentials || 0 }}</strong><p class="cp-metric-card__hint">Валидные / всего</p></article>
				<article class="cp-card cp-metric-card"><span class="cp-metric-card__label">Наборы данных</span><strong class="cp-metric-card__value">{{ summary.sync_entities || 0 }}</strong><p class="cp-metric-card__hint">Ошибок: {{ summary.sync_errors || 0 }}</p></article>
				<article class="cp-card cp-metric-card"><span class="cp-metric-card__label">Расчёт</span><strong class="cp-metric-card__value diagnostic-status-value">{{ statusText(summary.calculation_status) }}</strong><p class="cp-metric-card__hint">Прибыль: {{ summary.profit_complete === false ? 'неполная' : 'полная' }}</p></article>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Требует внимания</p><h3>Обнаруженные аномалии</h3></div><span class="cp-muted">{{ anomalies.length }}</span></div>
				<p v-if="anomalies.length === 0" class="cp-card-note">Автоматические проверки не нашли известных проблем.</p>
				<div v-else class="diagnostic-anomalies">
					<article v-for="item in anomalies" :key="`${item.code}-${JSON.stringify(item.details)}`" class="diagnostic-anomaly" :class="severityClass(item.severity)">
						<div><strong>{{ item.title }}</strong><code>{{ item.code }}</code></div>
						<pre>{{ safeJson(item.details) }}</pre>
					</article>
				</div>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Финансовая семантика</p><h3>Расчёт дашборда</h3></div><span class="cp-chip" :class="chipClass(calculation.status)">{{ statusText(calculation.status) }}</span></div>
				<p class="cp-card-note">Версия: {{ calculation.semantic_version || '—' }} · период {{ calculation.period_from || '—' }} — {{ calculation.period_to || '—' }} · кабинетов: {{ calculation.token_ids?.length || 0 }}</p>
				<p v-if="calculation.reason || calculation.message" class="diagnostic-error">{{ calculation.reason || calculation.message }}</p>
				<div v-if="calculation.metrics && Object.keys(calculation.metrics).length" class="diagnostic-calc-grid">
					<div><span>Продажи без СПП</span><strong>{{ formatMoney(calculation.metrics.sales_without_spp) }}</strong></div>
					<div><span>Продажи с СПП</span><strong>{{ formatMoney(calculation.metrics.sales_with_spp) }}</strong></div>
					<div><span>Возвраты</span><strong>{{ formatMoney(calculation.metrics.returns_amount) }}</strong></div>
					<div><span>Перечисление WB</span><strong>{{ formatMoney(calculation.metrics.ppvz_for_pay) }}</strong></div>
					<div><span>Комиссия</span><strong>{{ formatMoney(calculation.metrics.ppvz_sales_commission) }}</strong></div>
					<div><span>Логистика</span><strong>{{ formatMoney(calculation.metrics.delivery_rub) }}</strong></div>
					<div><span>Хранение</span><strong>{{ formatMoney(calculation.metrics.storage_fee) }}</strong></div>
					<div><span>Реклама</span><strong>{{ formatMoney(calculation.metrics.advertising_cost) }}</strong></div>
					<div><span>Налог</span><strong>{{ formatMoney(calculation.metrics.tax) }}</strong></div>
					<div><span>Себестоимость</span><strong>{{ formatMoney(calculation.metrics.product_cost) }}</strong></div>
					<div><span>Прочие расходы</span><strong>{{ formatMoney(calculation.metrics.other_expenses) }}</strong></div>
					<div><span>Прибыль</span><strong>{{ formatMoney(calculation.metrics.profit) }}</strong></div>
					<div><span>ДРР</span><strong>{{ calculation.metrics.drr }}%</strong></div>
					<div><span>Маржинальность</span><strong>{{ calculation.metrics.margin }}%</strong></div>
					<div><span>Нераспределённые расходы WB</span><strong>{{ formatMoney(calculation.metrics.unallocated_wb_expenses) }}</strong></div>
					<div><span>Покрытие себестоимости</span><strong>{{ calculation.cost_coverage_percent }}%</strong><small>Без стоимости: {{ calculation.products_without_cost || 0 }} товаров / {{ calculation.cost_missing_operations || 0 }} операций</small></div>
				</div>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Wildberries</p><h3>Подключения и полнота данных</h3></div></div>
				<div v-if="credentials.length === 0" class="cp-card-note">Кабинеты маркетплейса не подключены.</div>
				<div v-else class="diagnostic-credentials">
					<article v-for="credential in credentials" :key="credential.id" class="diagnostic-credential">
						<div class="diagnostic-row"><strong>{{ credential.label || credential.external_account_id || 'Кабинет WB' }}</strong><span class="cp-chip" :class="credential.is_valid ? 'cp-chip--active' : 'cp-chip--inactive'">{{ credential.is_valid ? 'Доступен' : 'Недоступен' }}</span></div>
						<div class="cp-muted diagnostic-meta">ID: {{ credential.id }} · тип: {{ credential.token_type || '—' }} · срок: {{ formatDate(credential.expires_at) }}</div>
						<div class="diagnostic-sync-grid">
							<div v-for="state in syncStates.filter(item => item.token_id === credential.id)" :key="state.id" class="diagnostic-sync-item">
								<strong>{{ state.entity }}</strong><span>Успех: {{ formatDate(state.last_success_at) }}</span><span v-if="state.last_error" class="diagnostic-error">{{ state.last_error }}</span><span v-else class="cp-muted">Последняя попытка: {{ formatDate(state.last_sync_at) }}</span>
							</div>
						</div>
					</article>
				</div>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Фоновые задания</p><h3>Последние синхронизации</h3></div><span class="cp-muted">{{ syncJobs.length }}</span></div>
				<div v-if="syncJobs.length === 0" class="cp-card-note">Задач синхронизации ещё нет.</div>
				<div v-else class="cp-table-wrap"><div class="cp-table-scroll"><table class="cp-table"><thead><tr><th>Создана</th><th>Данные</th><th>Статус</th><th>Попытка</th><th>Ошибка</th><th>ID</th></tr></thead><tbody><tr v-for="job in syncJobs" :key="job.id"><td>{{ formatDate(job.created_at) }}</td><td><strong>{{ job.entity }}</strong></td><td><span class="cp-chip" :class="chipClass(job.status)">{{ statusText(job.status) }}</span></td><td>{{ job.attempt_count }}</td><td class="diagnostic-error-cell">{{ job.error || '—' }}</td><td><code>{{ job.id }}</code></td></tr></tbody></table></div></div>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Эквайринг</p><h3>Платёжные операции</h3></div><span class="cp-muted">{{ payments.length }}</span></div>
				<div v-if="payments.length === 0" class="cp-card-note">Платёжных попыток нет.</div>
				<div v-else class="diagnostic-payments">
					<details v-for="payment in payments" :key="payment.id" class="diagnostic-details">
						<summary><span><strong>{{ payment.amount }} {{ payment.currency }}</strong> · {{ payment.provider }}</span><span class="cp-chip" :class="chipClass(payment.status)">{{ statusText(payment.status) }}</span></summary>
						<div class="diagnostic-details__body"><p class="cp-card-note">Payment ID: {{ payment.id }} · Provider ID: {{ payment.external_payment_id || '—' }} · статус провайдера: {{ payment.provider_status || '—' }}</p><ol class="diagnostic-events"><li v-for="event in payment.events" :key="event.id"><span>{{ formatDate(event.created_at) }}</span><strong>{{ event.event_type }}</strong><span>{{ event.provider_status || '—' }}</span><pre>{{ safeJson(event.provider_data) }}</pre></li></ol></div>
					</details>
				</div>
			</section>

			<section class="cp-card">
				<div class="diagnostic-section-head"><div><p class="cp-eyebrow">Корреляция</p><h3>Операционный журнал</h3></div><span class="cp-muted">{{ timeline.length }}</span></div>
				<div v-if="timeline.length === 0" class="cp-card-note">Новые трассируемые операции для пользователя ещё не зафиксированы.</div>
				<div v-else class="diagnostic-timeline">
					<details v-for="event in timeline" :key="event.id" class="diagnostic-details diagnostic-timeline__item">
						<summary><span class="diagnostic-time">{{ formatDate(event.created_at) }}</span><span><strong>{{ event.domain }} · {{ event.step }}</strong><small>{{ event.message || event.operation }}</small></span><span class="cp-chip" :class="chipClass(event.status)">{{ statusText(event.status) }}</span></summary>
						<div class="diagnostic-details__body diagnostic-grid"><div><span>Operation ID</span><code>{{ event.operation_id }}</code></div><div><span>Request ID</span><code>{{ event.request_id || '—' }}</code></div><div><span>Provider</span><strong>{{ event.provider || '—' }}</strong></div><div><span>HTTP / время</span><strong>{{ event.http_status || '—' }} · {{ event.duration_ms ?? '—' }} мс</strong></div><div><span>Ошибка</span><strong>{{ event.error_code || '—' }}</strong></div><div class="diagnostic-json"><span>Что отправлялось</span><pre>{{ safeJson(event.input) }}</pre></div><div class="diagnostic-json"><span>Что получено</span><pre>{{ safeJson(event.output) }}</pre></div><div class="diagnostic-json"><span>Метрики</span><pre>{{ safeJson(event.metrics) }}</pre></div></div>
					</details>
				</div>
			</section>
		</template>
	</section>
</template>

<style scoped>
.diagnostics-page { display: grid; gap: 1rem; }
.diagnostic-search { display: flex; align-items: end; gap: 0.75rem; }
.diagnostic-search__field { flex: 1; min-width: 0; }
.diagnostic-user, .diagnostic-row, .diagnostic-section-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.diagnostic-user h3, .diagnostic-section-head h3 { margin: 0; }
.diagnostic-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }
.diagnostic-status-value { font-size: 1.05rem; }
.diagnostic-calc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.65rem; margin-top: 1rem; }
.diagnostic-calc-grid > div { display: grid; gap: 0.2rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.diagnostic-calc-grid span, .diagnostic-calc-grid small { color: var(--text-muted); }
.diagnostic-anomalies, .diagnostic-credentials, .diagnostic-payments, .diagnostic-timeline { display: grid; gap: 0.75rem; margin-top: 1rem; }
.diagnostic-anomaly { border: 1px solid var(--border-color); border-radius: 12px; padding: 0.85rem; background: var(--surface-soft); }
.diagnostic-anomaly > div { display: flex; justify-content: space-between; gap: 1rem; }
.diagnostic-anomaly pre, .diagnostic-events pre, .diagnostic-json pre { margin: 0.55rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
.diagnostic-anomaly--critical, .diagnostic-anomaly--error { border-color: color-mix(in srgb, var(--danger-color, #c43d3d) 45%, var(--border-color)); }
.diagnostic-anomaly--warning { border-color: color-mix(in srgb, #c88a19 45%, var(--border-color)); }
.diagnostic-credential { border-top: 1px solid var(--border-color); padding-top: 0.9rem; }
.diagnostic-credential:first-child { border-top: 0; padding-top: 0; }
.diagnostic-meta { margin: 0.35rem 0 0.75rem; overflow-wrap: anywhere; }
.diagnostic-sync-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 0.5rem; }
.diagnostic-sync-item { display: grid; gap: 0.25rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 0.65rem; }
.diagnostic-error { color: var(--danger-color, #b63838); }
.diagnostic-error-cell { max-width: 360px; white-space: normal; }
.diagnostic-details { border: 1px solid var(--border-color); border-radius: 12px; overflow: clip; }
.diagnostic-details summary { cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.8rem; }
.diagnostic-details__body { border-top: 1px solid var(--border-color); padding: 0.8rem; }
.diagnostic-events { display: grid; gap: 0.6rem; margin: 0.75rem 0 0; padding-left: 1.25rem; }
.diagnostic-events li { padding-left: 0.25rem; }
.diagnostic-events li > span, .diagnostic-events li > strong { margin-right: 0.6rem; }
.diagnostic-timeline__item summary > span:nth-child(2) { display: grid; flex: 1; gap: 0.15rem; }
.diagnostic-time { min-width: 145px; font-size: 0.8rem; }
.diagnostic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.diagnostic-grid > div { display: grid; gap: 0.25rem; min-width: 0; }
.diagnostic-grid code { overflow-wrap: anywhere; }
.diagnostic-json { grid-column: span 2; }
@media (max-width: 900px) { .diagnostic-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) {
	.diagnostic-search, .diagnostic-user, .diagnostic-row, .diagnostic-section-head { align-items: stretch; flex-direction: column; }
	.diagnostic-summary, .diagnostic-grid { grid-template-columns: 1fr; }
	.diagnostic-json { grid-column: auto; }
	.diagnostic-details summary { align-items: flex-start; flex-direction: column; }
	.diagnostic-time { min-width: 0; }
}
</style>
