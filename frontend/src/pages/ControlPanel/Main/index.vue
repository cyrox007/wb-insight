<script setup>
import CP_Main from '@/API/ControlPanel/CP_Main'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const userCount = ref(0)
const accountHealth = ref({
	total: 0,
	active: 0,
	inactive: 0,
	verified: 0,
	unverified: 0,
	staff: 0,
})
const permissions = ref([])
const attention = ref({})
const isLoading = ref(false)
const loadError = ref('')

const isOverview = computed(() => route.name === 'control-panel.index')
const usersActive = computed(() => ['control-panel.users', 'control-panel.edit-user'].includes(route.name))
const rolesActive = computed(() => route.name === 'control-panel.roles')
const tariffsActive = computed(() => ['control-panel.tariffs', 'control-panel.edit-tariff'].includes(route.name))
const paymentsActive = computed(() => route.name === 'control-panel.payments')
const diagnosticsActive = computed(() => route.name === 'control-panel.diagnostics')
const mailActive = computed(() => route.name === 'control-panel.mail')
const auditActive = computed(() => route.name === 'control-panel.audit')
const can = (permission) => permissions.value.includes(permission)

const attentionCount = computed(() => {
	const mail = attention.value?.mail || {}
	const payments = attention.value?.payments || {}
	const system = attention.value?.system || {}
	return Number(mail.failed_recent || 0)
		+ Number(mail.stale_queued || 0)
		+ Number(payments.failed_24h || 0)
		+ Number(payments.pending_over_24h || 0)
		+ Number(system.issue_count || 0)
})

const attentionHint = computed(() => {
	const parts = []
	const payments = attention.value?.payments || {}
	const mail = attention.value?.mail || {}
	const system = attention.value?.system || {}
	if (Number(payments.failed_24h || 0) + Number(payments.pending_over_24h || 0) > 0) {
		parts.push(`платежи: ${Number(payments.failed_24h || 0) + Number(payments.pending_over_24h || 0)}`)
	}
	if (Number(mail.failed_recent || 0) + Number(mail.stale_queued || 0) > 0) {
		parts.push(`почта: ${Number(mail.failed_recent || 0) + Number(mail.stale_queued || 0)}`)
	}
	if (Number(system.issue_count || 0) > 0) parts.push(`система: ${Number(system.issue_count)}`)
	return parts.join(' · ') || 'Откройте центр инцидентов для подробной проверки'
})

const diagnosticsContextLink = computed(() => {
	if (route.name === 'control-panel.edit-user' && route.params.id) {
		return {
			label: 'Диагностика пользователя',
			to: { name: 'control-panel.diagnostics', query: { user_query: String(route.params.id) } },
		}
	}
	if (route.name === 'control-panel.edit-tariff' && route.params.id) {
		return {
			label: 'Диагностика тарифа',
			to: { name: 'control-panel.diagnostics', query: { tariff_query: String(route.params.id) } },
		}
	}
	return null
})

async function loadOverview() {
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Main.getControlPanel()
		if (response.data?.status !== 'success') throw new Error('Некорректный ответ API панели управления')
		userCount.value = Number(response.data?.user_count || 0)
		accountHealth.value = {
			...accountHealth.value,
			...(response.data?.account_health || {}),
		}
		permissions.value = Array.isArray(response.data?.permissions) ? response.data.permissions : []
		attention.value = response.data?.attention || {}
	} catch (error) {
		console.error('Ошибка загрузки панели управления:', error)
		loadError.value = 'Не удалось загрузить сводку панели управления.'
	} finally {
		isLoading.value = false
	}
}

onMounted(loadOverview)
</script>

<template>
	<section class="cp-shell">
		<header class="cp-shell__header">
			<div>
				<p class="cp-eyebrow">WB Insight · управление</p>
				<h1 class="cp-title">Панель управления</h1>
				<p class="cp-subtitle">Пользователи, роли, тарифы, платежи, диагностика, рассылки и аудит в едином административном интерфейсе.</p>
			</div>
			<router-link
				v-if="diagnosticsContextLink && can('diagnostics:read')"
				:to="diagnosticsContextLink.to"
				class="cp-context-diagnostics"
			>
				{{ diagnosticsContextLink.label }} →
			</router-link>
		</header>

		<nav class="cp-nav" aria-label="Разделы панели управления">
			<router-link :to="{ name: 'control-panel.index' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': isOverview }" :aria-current="isOverview ? 'page' : undefined">Обзор</router-link>
			<router-link v-if="can('users:read')" :to="{ name: 'control-panel.users' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': usersActive }" :aria-current="usersActive ? 'page' : undefined">Пользователи</router-link>
			<router-link v-if="can('roles:read')" :to="{ name: 'control-panel.roles' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': rolesActive }" :aria-current="rolesActive ? 'page' : undefined">Роли</router-link>
			<router-link v-if="can('tariffs:read')" :to="{ name: 'control-panel.tariffs' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': tariffsActive }" :aria-current="tariffsActive ? 'page' : undefined">Тарифы</router-link>
			<router-link v-if="can('payments:read')" :to="{ name: 'control-panel.payments' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': paymentsActive }" :aria-current="paymentsActive ? 'page' : undefined">Платежи</router-link>
			<router-link v-if="can('diagnostics:read')" :to="{ name: 'control-panel.diagnostics' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': diagnosticsActive }" :aria-current="diagnosticsActive ? 'page' : undefined">Диагностика</router-link>
			<router-link v-if="can('mail:read')" :to="{ name: 'control-panel.mail' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': mailActive }" :aria-current="mailActive ? 'page' : undefined">Рассылки</router-link>
			<router-link v-if="can('audit:read')" :to="{ name: 'control-panel.audit' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': auditActive }" :aria-current="auditActive ? 'page' : undefined">Аудит</router-link>
		</nav>

		<Transition name="cp-page-motion" mode="out-in">
			<div v-if="isOverview" key="overview" class="cp-page">
			<div v-if="isLoading" class="cp-state" role="status">Загружаем административную сводку…</div>
			<div v-else-if="loadError" class="cp-state cp-state--error" role="alert"><div class="cp-state__stack"><strong>{{ loadError }}</strong><BaseButton variant="outline" size="small" text="Повторить" @click="loadOverview" /></div></div>

			<template v-else>
				<section class="cp-health-grid" aria-label="Состояние аккаунтов">
					<article class="cp-card cp-metric-card">
						<span class="cp-metric-card__label">Аккаунты</span>
						<strong class="cp-metric-card__value">{{ accountHealth.total || userCount }}</strong>
						<p class="cp-metric-card__hint">Всего зарегистрировано</p>
					</article>
					<article class="cp-card cp-metric-card">
						<span class="cp-metric-card__label">Активны</span>
						<strong class="cp-metric-card__value">{{ accountHealth.active }}</strong>
						<p class="cp-metric-card__hint">Доступ к сервису разрешён</p>
					</article>
					<article class="cp-card cp-metric-card">
						<span class="cp-metric-card__label">Без верификации</span>
						<strong class="cp-metric-card__value">{{ accountHealth.unverified }}</strong>
						<p class="cp-metric-card__hint">Email ещё не подтверждён</p>
					</article>
					<article class="cp-card cp-metric-card">
						<span class="cp-metric-card__label">Деактивированы</span>
						<strong class="cp-metric-card__value">{{ accountHealth.inactive }}</strong>
						<p class="cp-metric-card__hint">Доступ к аккаунту остановлен</p>
					</article>
				</section>

				<router-link
					v-if="can('diagnostics:read') && attentionCount > 0"
					:to="{ name: 'control-panel.diagnostics' }"
					class="cp-card cp-attention-card"
				>
					<div>
						<span class="cp-eyebrow">Требует внимания</span>
						<strong>{{ attentionCount }} сигналов</strong>
						<p class="cp-card-note">{{ attentionHint }}</p>
					</div>
					<span class="cp-shortcut-card__action">Разобрать инциденты →</span>
				</router-link>

				<section class="cp-overview-grid cp-overview-grid--shortcuts">
					<router-link v-if="can('users:read')" :to="{ name: 'control-panel.users' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Аккаунты</span><h2 class="cp-shortcut-card__title">Управление пользователями</h2><p class="cp-card-note">Статус, профиль, верификация и безопасность аккаунтов.</p></div><span class="cp-shortcut-card__action">Открыть пользователей →</span></router-link>
					<router-link v-if="can('roles:read')" :to="{ name: 'control-panel.roles' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Доступ</span><h2 class="cp-shortcut-card__title">Роли и права</h2><p class="cp-card-note">Матрица доступа и назначения системных ролей.</p></div><span class="cp-shortcut-card__action">Открыть роли →</span></router-link>
					<router-link v-if="can('tariffs:read')" :to="{ name: 'control-panel.tariffs' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Монетизация</span><h2 class="cp-shortcut-card__title">Тарифные планы</h2><p class="cp-card-note">Стоимость, доступность и продуктовые лимиты.</p></div><span class="cp-shortcut-card__action">Открыть тарифы →</span></router-link>
					<router-link v-if="can('payments:read')" :to="{ name: 'control-panel.payments' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Платежи</span><h2 class="cp-shortcut-card__title">Платёжные системы</h2><p class="cp-card-note">Test/live режимы, учётные данные и журнал оплат тарифов.</p></div><span class="cp-shortcut-card__action">Открыть платежи →</span></router-link>
					<router-link v-if="can('diagnostics:read')" :to="{ name: 'control-panel.diagnostics' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Поддержка</span><h2 class="cp-shortcut-card__title">Диагностика пользователя</h2><p class="cp-card-note">Платежи, кабинеты WB, полнота данных, фоновые задания и единая временная шкала.</p></div><span class="cp-shortcut-card__action">Открыть диагностику →</span></router-link>
					<router-link v-if="can('mail:read')" :to="{ name: 'control-panel.mail' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Коммуникации</span><h2 class="cp-shortcut-card__title">Рассылки</h2><p class="cp-card-note">Транзакционная почта, кампании и журнал доставки.</p></div><span class="cp-shortcut-card__action">Открыть рассылки →</span></router-link>
					<router-link v-if="can('audit:read')" :to="{ name: 'control-panel.audit' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Инциденты</span><h2 class="cp-shortcut-card__title">Аудит действий</h2><p class="cp-card-note">Кто, когда и что изменил — с результатом и request-корреляцией.</p></div><span class="cp-shortcut-card__action">Открыть аудит →</span></router-link>
				</section>

				<div v-if="permissions.length === 1 && can('control_panel:access')" class="cp-info-callout">
					<strong>Для этой роли доступна безопасная операционная сводка.</strong>
					<span>Клиентские карточки, платежи и другие чувствительные разделы не открываются без отдельного backend permission.</span>
				</div>
			</template>
			</div>

			<div v-else :key="String(route.name || route.path)" class="cp-route-frame">
				<RouterView />
			</div>
		</Transition>
	</section>
</template>

<style scoped>
.cp-shell__header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 1rem;
}

.cp-context-diagnostics {
	flex: 0 0 auto;
	border: 1px solid var(--border-color);
	border-radius: 10px;
	background: var(--surface-soft);
	color: var(--text-color);
	padding: 0.6rem 0.8rem;
	text-decoration: none;
}

.cp-context-diagnostics:hover {
	border-color: var(--primary-color);
}

.cp-attention-card {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	text-decoration: none;
	color: var(--text-color);
	border-color: color-mix(in srgb, var(--danger-color, #c43d3d) 30%, var(--border-color));
}

.cp-attention-card strong {
	display: block;
	font-size: 1.3rem;
	margin-top: 0.15rem;
}


.cp-route-frame {
	min-width: 0;
	transform-origin: 50% 10%;
	will-change: opacity, transform;
}

.cp-page-motion-enter-active {
	transition:
		opacity 220ms ease-out,
		transform 260ms cubic-bezier(0.22, 1, 0.36, 1);
}

.cp-page-motion-leave-active {
	transition:
		opacity 125ms ease-in,
		transform 145ms ease-in;
}

.cp-page-motion-enter-from {
	opacity: 0;
	transform: translateY(8px) scale(0.997);
}

.cp-page-motion-leave-to {
	opacity: 0;
	transform: translateY(-3px) scale(0.999);
}

@media (max-width: 720px) {
	.cp-shell__header {
		flex-direction: column;
	}

	.cp-context-diagnostics {
		width: 100%;
	}
}

@media (prefers-reduced-motion: reduce) {
	.cp-page-motion-enter-active,
	.cp-page-motion-leave-active {
		transition: none;
	}

	.cp-page-motion-enter-from,
	.cp-page-motion-leave-to {
		opacity: 1;
		transform: none;
	}
}
</style>
