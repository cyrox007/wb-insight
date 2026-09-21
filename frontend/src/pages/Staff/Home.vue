<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CP_Main from '@/API/ControlPanel/CP_Main'
import { ROLE_LABELS } from '@/security/roles'

const authStore = useAuthStore()
const loading = ref(false)
const errorMessage = ref('')
const permissions = ref([])
const attention = ref({})
const health = ref({
	total: 0,
	active: 0,
	inactive: 0,
	verified: 0,
	unverified: 0,
	staff: 0,
})

const roles = computed(() => authStore.user?.roles || [])
const primaryRole = computed(() => {
	const priority = ['super_admin', 'admin', 'manager', 'support', 'analyst']
	return priority.find((role) => roles.value.includes(role)) || 'user'
})

const workspaceCopy = computed(() => {
	const map = {
		super_admin: {
			eyebrow: 'Система · полный контроль',
			title: 'Операционный центр',
			subtitle: 'Состояние клиентских аккаунтов, доступы, платежи, коммуникации и аудит — без перегруза продавцовской аналитикой.',
		},
		admin: {
			eyebrow: 'Администрирование',
			title: 'Рабочий стол администратора',
			subtitle: 'Пользователи, тарифы, платежи и коммуникации собраны в приоритетном административном контуре.',
		},
		manager: {
			eyebrow: 'Клиенты · операции',
			title: 'Рабочий стол менеджера',
			subtitle: 'Сосредоточьтесь на состоянии клиентских аккаунтов, тарифах и обращениях. Аналитика продавца остаётся доступна как режим просмотра.',
		},
		support: {
			eyebrow: 'Поддержка клиентов',
			title: 'Рабочий стол поддержки',
			subtitle: 'Быстрый доступ к аккаунтам и журналу действий для диагностики проблем пользователей.',
		},
		analyst: {
			eyebrow: 'Контроль продукта',
			title: 'Рабочий стол аналитика',
			subtitle: 'Сводное состояние клиентской базы и быстрый переход к интерфейсу аналитики для проверки продукта.',
		},
	}
	return map[primaryRole.value] || map.analyst
})

const can = (permission) => permissions.value.includes(permission)

const attentionCards = computed(() => {
	const items = []
	const users = attention.value?.users
	const mail = attention.value?.mail
	const payments = attention.value?.payments
	const system = attention.value?.system

	if (users?.unverified > 0) {
		items.push({
			key: 'unverified',
			count: users.unverified,
			label: 'Email не подтверждён',
			text: 'Аккаунты ожидают подтверждения email.',
			to: { name: 'control-panel.users' },
			tone: 'warning',
		})
	}
	if (users?.inactive > 0) {
		items.push({
			key: 'inactive',
			count: users.inactive,
			label: 'Неактивные аккаунты',
			text: 'Клиентские аккаунты с остановленным доступом.',
			to: { name: 'control-panel.users' },
			tone: 'neutral',
		})
	}
	if (mail?.failed_recent > 0) {
		items.push({
			key: 'mail-failed',
			count: mail.failed_recent,
			label: 'Ошибки почты',
			text: `Ошибки за последние ${mail.failure_lookback_minutes || '—'} мин.`,
			to: { name: 'control-panel.mail' },
			tone: 'danger',
		})
	}
	if (mail?.stale_queued > 0) {
		items.push({
			key: 'mail-stale',
			count: mail.stale_queued,
			label: 'Зависшие письма',
			text: `Очередь старше ${mail.queue_stale_minutes || '—'} мин.`,
			to: { name: 'control-panel.mail' },
			tone: 'warning',
		})
	}
	if (payments?.failed_24h > 0) {
		items.push({
			key: 'payments-failed',
			count: payments.failed_24h,
			label: 'Ошибки платежей',
			text: 'Неуспешные платёжные попытки за 24 часа.',
			to: { name: 'control-panel.payments' },
			tone: 'danger',
		})
	}
	if (payments?.pending_over_24h > 0) {
		items.push({
			key: 'payments-pending',
			count: payments.pending_over_24h,
			label: 'Долго ожидают оплаты',
			text: 'Платёжные попытки остаются pending более 24 часов.',
			to: { name: 'control-panel.payments' },
			tone: 'warning',
		})
	}
	if (system?.issue_count > 0) {
		items.push({
			key: 'system',
			count: system.issue_count,
			label: 'Системные сигналы',
			text: `Operations status: ${system.status || 'unknown'}.`,
			to: { name: 'control-panel.index' },
			tone: system.status === 'degraded' ? 'danger' : 'warning',
		})
	}

	return items
})

const hasAttentionScope = computed(() => Object.keys(attention.value || {}).length > 0)

const actionCards = computed(() => {
	const items = [
		{
			permission: 'users:read',
			to: { name: 'control-panel.users' },
			kicker: 'Клиенты',
			title: 'Аккаунты пользователей',
			text: 'Статус, роли, верификация, профиль и доступ пользователей.',
			action: 'Открыть пользователей →',
		},
		{
			permission: 'payments:read',
			to: { name: 'control-panel.payments' },
			kicker: 'Монетизация',
			title: 'Платежи',
			text: 'Платёжные попытки, провайдеры и состояние оплат.',
			action: 'Открыть платежи →',
		},
		{
			permission: 'tariffs:read',
			to: { name: 'control-panel.tariffs' },
			kicker: 'Продукт',
			title: 'Тарифы',
			text: 'Планы, лимиты и доступность коммерческих предложений.',
			action: 'Открыть тарифы →',
		},
		{
			permission: 'mail:read',
			to: { name: 'control-panel.mail' },
			kicker: 'Коммуникации',
			title: 'Рассылки',
			text: 'Почтовый шлюз, кампании и журнал доставки сообщений.',
			action: 'Открыть рассылки →',
		},
		{
			permission: 'audit:read',
			to: { name: 'control-panel.audit' },
			kicker: 'Контроль',
			title: 'Аудит действий',
			text: 'Административные изменения, ошибки и корреляция действий.',
			action: 'Открыть аудит →',
		},
	]
	return items.filter((item) => can(item.permission))
})

async function loadWorkspace() {
	loading.value = true
	errorMessage.value = ''
	try {
		const response = await CP_Main.getControlPanel()
		if (response.data?.status !== 'success') throw new Error('Некорректный ответ API')
		permissions.value = Array.isArray(response.data?.permissions) ? response.data.permissions : []
		health.value = { ...health.value, ...(response.data?.client_health || response.data?.account_health || {}) }
		attention.value = response.data?.attention || {}
	} catch (error) {
		console.error('Ошибка загрузки рабочего стола сотрудника:', error)
		errorMessage.value = error.response?.data?.error?.message || 'Не удалось загрузить операционную сводку.'
	} finally {
		loading.value = false
	}
}

onMounted(loadWorkspace)
</script>

<template>
	<section class="staff-page">
		<header class="staff-hero">
			<div>
				<p class="staff-eyebrow">{{ workspaceCopy.eyebrow }}</p>
				<h1>{{ workspaceCopy.title }}</h1>
				<p class="staff-subtitle">{{ workspaceCopy.subtitle }}</p>
			</div>
			<div class="staff-identity">
				<span>Текущая роль</span>
				<strong>{{ ROLE_LABELS[primaryRole] || primaryRole }}</strong>
			</div>
		</header>

		<div v-if="loading" class="staff-state">Загружаем рабочую область…</div>
		<div v-else-if="errorMessage" class="staff-state staff-state--error">
			<strong>{{ errorMessage }}</strong>
			<button type="button" @click="loadWorkspace">Повторить</button>
		</div>

		<template v-else>
			<section class="health-grid" aria-label="Состояние пользовательских аккаунтов">
				<article>
					<span>Клиенты</span>
					<strong>{{ health.total }}</strong>
					<small>Клиентских аккаунтов в системе</small>
				</article>
				<article>
					<span>Активны</span>
					<strong>{{ health.active }}</strong>
					<small>Активные клиентские аккаунты</small>
				</article>
				<article>
					<span>Без верификации</span>
					<strong>{{ health.unverified }}</strong>
					<small>Клиенты ожидают подтверждения email</small>
				</article>
				<article>
					<span>Деактивированы</span>
					<strong>{{ health.inactive }}</strong>
					<small>Клиентский доступ остановлен</small>
				</article>
			</section>

			<section v-if="hasAttentionScope" class="staff-section">
				<div class="section-heading">
					<div>
						<p class="staff-eyebrow">Операционная сводка</p>
						<h2>Требует внимания</h2>
					</div>
				</div>

				<div v-if="attentionCards.length" class="attention-grid">
					<RouterLink
						v-for="item in attentionCards"
						:key="item.key"
						:to="item.to"
						class="attention-card"
						:class="`attention-card--${item.tone}`"
					>
						<strong>{{ item.count }}</strong>
						<div>
							<span>{{ item.label }}</span>
							<small>{{ item.text }}</small>
						</div>
						<b aria-hidden="true">→</b>
					</RouterLink>
				</div>
				<div v-else class="staff-empty staff-empty--healthy">
					<strong>По доступным вашей роли сигналам проблем не найдено.</strong>
					<span>Сводка строится только из агрегатов, на которые у текущей роли есть backend permission.</span>
				</div>
			</section>

			<section class="staff-section">
				<div class="section-heading">
					<div>
						<p class="staff-eyebrow">Приоритеты роли</p>
						<h2>Рабочие инструменты</h2>
					</div>
					<RouterLink :to="{ name: 'control-panel.index' }" class="text-link">Вся панель управления →</RouterLink>
				</div>

				<div v-if="actionCards.length" class="action-grid">
					<RouterLink v-for="item in actionCards" :key="item.title" :to="item.to" class="action-card">
						<div>
							<span>{{ item.kicker }}</span>
							<h3>{{ item.title }}</h3>
							<p>{{ item.text }}</p>
						</div>
						<strong>{{ item.action }}</strong>
					</RouterLink>
				</div>
				<div v-else class="staff-empty">
					Для этой роли административные разделы доступны только в режиме общей сводки.
				</div>
			</section>

			<section class="staff-section staff-section--secondary">
				<div class="section-heading">
					<div>
						<p class="staff-eyebrow">Вторичный режим</p>
						<h2>Клиентская аналитика</h2>
					</div>
				</div>
				<div class="analytics-preview">
					<div>
						<strong>Интерфейс продавца остаётся доступен для проверки продукта.</strong>
						<p>Для сотрудников он не является стартовой рабочей областью. Данные клиентов не подменяются и не открываются через frontend — tenant-доступ по-прежнему контролируется backend.</p>
					</div>
					<RouterLink :to="{ name: 'dashboard.home' }" class="secondary-action">Открыть аналитику →</RouterLink>
				</div>
			</section>
		</template>
	</section>
</template>

<style scoped>
.staff-page {
	width: min(100% - 32px, var(--content-width));
	margin: 0 auto;
	padding: 24px 0 52px;
}

.staff-hero {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 28px;
	padding: 22px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius-lg);
	background:
		radial-gradient(circle at 88% 10%, color-mix(in srgb, var(--secondary-color) 14%, transparent), transparent 19rem),
		linear-gradient(180deg, var(--card-bg-elevated), var(--card-bg));
	box-shadow: var(--shadow-sm);
}

.staff-eyebrow {
	color: var(--secondary-color);
	font-size: 10px;
	font-weight: 800;
	letter-spacing: .09em;
	text-transform: uppercase;
}

.staff-hero h1 {
	margin-top: 4px;
	font-size: clamp(28px, 3vw, 40px);
	letter-spacing: -.04em;
}

.staff-subtitle {
	max-width: 760px;
	margin-top: 9px;
	color: var(--text-muted);
	font-size: 14px;
	line-height: 1.6;
}

.staff-identity {
	flex: 0 0 auto;
	min-width: 170px;
	padding: 12px 14px;
	border: 1px solid var(--border-color);
	border-radius: 11px;
	background: var(--light-bg);
}

.staff-identity span,
.health-grid span {
	display: block;
	color: var(--text-subtle);
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .06em;
}

.staff-identity strong {
	display: block;
	margin-top: 5px;
	font-size: 14px;
}

.staff-state {
	margin-top: 14px;
	padding: 18px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--card-bg);
	color: var(--text-muted);
}

.staff-state--error {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 14px;
	color: var(--danger-color);
}

.staff-state button {
	padding: 7px 11px;
	border: 1px solid var(--border-color);
	border-radius: 8px;
	background: var(--card-bg);
	color: var(--text-color);
	cursor: pointer;
}

.health-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 10px;
	margin-top: 14px;
}

.health-grid article {
	min-height: 126px;
	padding: 16px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--card-bg);
	box-shadow: var(--shadow-sm);
}

.health-grid strong {
	display: block;
	margin-top: 16px;
	font-size: 28px;
	letter-spacing: -.03em;
}

.health-grid small {
	display: block;
	margin-top: 9px;
	color: var(--text-muted);
	font-size: 11px;
}

.attention-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}

.attention-card {
	min-height: 110px;
	padding: 15px;
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	align-items: center;
	gap: 12px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--card-bg);
	box-shadow: var(--shadow-sm);
	transition: transform var(--transition), border-color var(--transition);
}

.attention-card:hover {
	transform: translateY(-1px);
	border-color: color-mix(in srgb, var(--secondary-color) 30%, var(--border-color));
}

.attention-card > strong {
	min-width: 42px;
	font-size: 28px;
	letter-spacing: -.04em;
}

.attention-card > div {
	min-width: 0;
	display: grid;
	gap: 4px;
}

.attention-card span {
	font-size: 12px;
	font-weight: 760;
}

.attention-card small {
	color: var(--text-muted);
	font-size: 10px;
	line-height: 1.4;
}

.attention-card b {
	color: var(--text-subtle);
	font-size: 16px;
}

.attention-card--danger {
	border-color: color-mix(in srgb, var(--danger-color) 26%, var(--border-color));
	background: color-mix(in srgb, var(--danger-color) 5%, var(--card-bg));
}

.attention-card--warning {
	border-color: color-mix(in srgb, var(--warning-color) 26%, var(--border-color));
	background: color-mix(in srgb, var(--warning-color) 5%, var(--card-bg));
}

.staff-empty--healthy {
	display: grid;
	gap: 5px;
	border-style: dashed;
}

.staff-empty--healthy strong {
	color: var(--text-color);
	font-size: 13px;
}

.staff-empty--healthy span {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.45;
}

.staff-section {
	margin-top: 24px;
}

.staff-section--secondary {
	margin-top: 30px;
}

.section-heading {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 20px;
	margin-bottom: 10px;
}

.section-heading h2 {
	margin-top: 3px;
	font-size: 20px;
	letter-spacing: -.02em;
}

.text-link,
.secondary-action {
	color: var(--secondary-color);
	font-size: 12px;
	font-weight: 750;
}

.action-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}

.action-card {
	min-height: 180px;
	padding: 18px;
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	gap: 18px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--card-bg);
	box-shadow: var(--shadow-sm);
	transition: transform var(--transition), border-color var(--transition);
}

.action-card:hover {
	transform: translateY(-2px);
	border-color: color-mix(in srgb, var(--secondary-color) 35%, var(--border-color));
}

.action-card span {
	color: var(--secondary-color);
	font-size: 10px;
	font-weight: 800;
	text-transform: uppercase;
	letter-spacing: .07em;
}

.action-card h3 {
	margin-top: 6px;
	font-size: 16px;
}

.action-card p {
	margin-top: 7px;
	color: var(--text-muted);
	font-size: 12px;
	line-height: 1.5;
}

.action-card > strong {
	color: var(--secondary-color);
	font-size: 11px;
}

.staff-empty,
.analytics-preview {
	padding: 18px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--card-bg);
}

.staff-empty {
	color: var(--text-muted);
	font-size: 13px;
}

.analytics-preview {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 24px;
}

.analytics-preview strong {
	font-size: 14px;
}

.analytics-preview p {
	max-width: 780px;
	margin-top: 6px;
	color: var(--text-muted);
	font-size: 12px;
	line-height: 1.55;
}

.secondary-action {
	flex: 0 0 auto;
	padding: 9px 12px;
	border: 1px solid var(--border-color);
	border-radius: 9px;
	background: var(--light-bg);
}

@media (max-width: 980px) {
	.health-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.action-grid,
	.attention-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}

@media (max-width: 700px) {
	.staff-page {
		width: min(100% - 20px, var(--content-width));
		padding-top: 14px;
	}
	.staff-hero,
	.analytics-preview,
	.section-heading {
		align-items: stretch;
		flex-direction: column;
	}
	.staff-identity {
		min-width: 0;
	}
	.action-grid,
	.attention-grid {
		grid-template-columns: 1fr;
	}
}

@media (max-width: 440px) {
	.health-grid {
		grid-template-columns: 1fr;
	}
}
</style>
