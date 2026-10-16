<script setup>
const props = defineProps({
	events: { type: Array, default: () => [] },
	title: { type: String, default: 'Временная шкала' },
	subtitle: { type: String, default: '' },
	total: { type: Number, default: null },
	loading: { type: Boolean, default: false },
})

const emit = defineEmits(['open-operation', 'open-request'])

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
</script>

<template>
	<section class="cp-card diagnostic-timeline">
		<div class="diagnostic-timeline__head">
			<div>
				<p class="cp-eyebrow">Операционный журнал</p>
				<h3>{{ title }}</h3>
				<p v-if="subtitle" class="cp-card-note">{{ subtitle }}</p>
			</div>
			<span class="cp-muted">{{ total ?? events.length }} событий</span>
		</div>

		<div v-if="loading" class="cp-state" role="status">Загружаем события…</div>
		<p v-else-if="!events.length" class="cp-card-note">По выбранным условиям событий нет.</p>

		<div v-else class="diagnostic-events">
			<details v-for="event in events" :key="event.id" class="diagnostic-event">
				<summary>
					<span class="diagnostic-event__time">{{ formatDate(event.created_at) }}</span>
					<span class="diagnostic-event__name">
						<strong>{{ event.component || event.domain }} · {{ event.step }}</strong>
						<small>{{ event.message || event.operation }}</small>
					</span>
					<span class="cp-chip" :class="statusClass(event.status)">{{ event.status }}</span>
				</summary>

				<div class="diagnostic-event__body">
					<div class="diagnostic-event-grid">
						<div><span>Последовательность</span><strong>#{{ event.sequence_no ?? '—' }} · {{ event.event_kind || '—' }} · {{ event.direction || '—' }}</strong></div>
						<div><span>HTTP / время</span><strong>{{ event.http_status || '—' }} · {{ event.duration_ms ?? '—' }} мс</strong></div>
						<div><span>Операция</span><code>{{ event.operation_id }}</code></div>
						<div><span>Родитель</span><code>{{ event.parent_operation_id || '—' }}</code></div>
						<div><span>Запрос</span><code>{{ event.request_id || '—' }}</code></div>
						<div><span>Пользователь</span><code>{{ event.user_id || '—' }}</code></div>
						<div><span>Инициатор</span><code>{{ event.actor_user_id || '—' }}</code></div>
						<div><span>Субъект</span><code>{{ event.subject_type || '—' }} · {{ event.subject_id || '—' }}</code></div>
						<div><span>Провайдер</span><strong>{{ event.provider || '—' }}</strong></div>
						<div><span>Ошибка</span><strong>{{ event.error_code || '—' }}</strong></div>
					</div>

					<div class="diagnostic-event-actions">
						<button v-if="event.operation_id" type="button" @click="emit('open-operation', event.operation_id)">Открыть всю операцию</button>
						<button v-if="event.request_id" type="button" @click="emit('open-request', event.request_id)">Открыть HTTP-запрос</button>
					</div>

					<div class="diagnostic-payloads">
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

<style scoped>
.diagnostic-timeline { display: grid; gap: 0.8rem; }
.diagnostic-timeline__head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.diagnostic-timeline__head h3 { margin: 0; }
.diagnostic-events { display: grid; gap: 0.65rem; }
.diagnostic-event { border: 1px solid var(--border-color); border-radius: 12px; overflow: clip; }
.diagnostic-event summary { cursor: pointer; display: flex; align-items: center; gap: 0.8rem; padding: 0.75rem; }
.diagnostic-event__time { min-width: 145px; font-size: 0.8rem; color: var(--text-muted); }
.diagnostic-event__name { display: grid; flex: 1; gap: 0.1rem; }
.diagnostic-event__name small { color: var(--text-muted); }
.diagnostic-event__body { border-top: 1px solid var(--border-color); padding: 0.8rem; }
.diagnostic-event-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; }
.diagnostic-event-grid > div { display: grid; gap: 0.2rem; min-width: 0; }
.diagnostic-event-grid span, .diagnostic-payloads span { color: var(--text-muted); }
.diagnostic-event-grid code { overflow-wrap: anywhere; }
.diagnostic-event-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.8rem; }
.diagnostic-event-actions button { border: 1px solid var(--border-color); border-radius: 8px; background: var(--surface-soft); color: var(--text-color); padding: 0.4rem 0.65rem; cursor: pointer; }
.diagnostic-payloads { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; margin-top: 0.8rem; }
.diagnostic-payloads > div { min-width: 0; }
.diagnostic-payloads pre { margin: 0.3rem 0 0; max-height: 360px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 0.75rem; }
@media (max-width: 760px) {
	.diagnostic-event summary { align-items: flex-start; flex-wrap: wrap; }
	.diagnostic-event__time { min-width: 0; width: 100%; }
	.diagnostic-event-grid, .diagnostic-payloads { grid-template-columns: 1fr; }
}
</style>
