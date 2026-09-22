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
const isLoading = ref(false)
const loadError = ref('')

const isOverview = computed(() => route.name === 'control-panel.index')
const usersActive = computed(() => ['control-panel.users', 'control-panel.edit-user'].includes(route.name))
const rolesActive = computed(() => route.name === 'control-panel.roles')
const tariffsActive = computed(() => ['control-panel.tariffs', 'control-panel.edit-tariff'].includes(route.name))
const paymentsActive = computed(() => route.name === 'control-panel.payments')
const mailActive = computed(() => route.name === 'control-panel.mail')
const auditActive = computed(() => route.name === 'control-panel.audit')
const can = (permission) => permissions.value.includes(permission)

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
				<p class="cp-subtitle">Пользователи, роли, тарифы, платежи, рассылки, аудит и системные настройки в едином административном интерфейсе.</p>
			</div>
		</header>

		<nav class="cp-nav" aria-label="Разделы панели управления">
			<router-link :to="{ name: 'control-panel.index' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': isOverview }" :aria-current="isOverview ? 'page' : undefined">Обзор</router-link>
			<router-link v-if="can('users:read')" :to="{ name: 'control-panel.users' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': usersActive }" :aria-current="usersActive ? 'page' : undefined">Пользователи</router-link>
			<router-link v-if="can('roles:read')" :to="{ name: 'control-panel.roles' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': rolesActive }" :aria-current="rolesActive ? 'page' : undefined">Роли</router-link>
			<router-link v-if="can('tariffs:read')" :to="{ name: 'control-panel.tariffs' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': tariffsActive }" :aria-current="tariffsActive ? 'page' : undefined">Тарифы</router-link>
			<router-link v-if="can('payments:read')" :to="{ name: 'control-panel.payments' }" class="cp-nav__link" active-class="" :class="{ 'router-link-active': paymentsActive }" :aria-current="paymentsActive ? 'page' : undefined">Платежи</router-link>
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

				<section class="cp-overview-grid cp-overview-grid--shortcuts">
					<router-link v-if="can('users:read')" :to="{ name: 'control-panel.users' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Аккаунты</span><h2 class="cp-shortcut-card__title">Управление пользователями</h2><p class="cp-card-note">Статус, профиль, верификация и безопасность аккаунтов.</p></div><span class="cp-shortcut-card__action">Открыть пользователей →</span></router-link>
					<router-link v-if="can('roles:read')" :to="{ name: 'control-panel.roles' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Доступ</span><h2 class="cp-shortcut-card__title">Роли и права</h2><p class="cp-card-note">Матрица доступа и назначения системных ролей.</p></div><span class="cp-shortcut-card__action">Открыть роли →</span></router-link>
					<router-link v-if="can('tariffs:read')" :to="{ name: 'control-panel.tariffs' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Монетизация</span><h2 class="cp-shortcut-card__title">Тарифные планы</h2><p class="cp-card-note">Стоимость, доступность и продуктовые лимиты.</p></div><span class="cp-shortcut-card__action">Открыть тарифы →</span></router-link>
					<router-link v-if="can('payments:read')" :to="{ name: 'control-panel.payments' }" class="cp-card cp-shortcut-card"><div><span class="cp-eyebrow">Платежи</span><h2 class="cp-shortcut-card__title">Платёжные системы</h2><p class="cp-card-note">Test/live режимы, credentials и журнал оплат тарифов.</p></div><span class="cp-shortcut-card__action">Открыть платежи →</span></router-link>
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
