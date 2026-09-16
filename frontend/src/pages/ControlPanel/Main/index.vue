<script setup>
import CP_Main from '@/API/ControlPanel/CP_Main'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const userCount = ref(0)
const isLoading = ref(false)
const loadError = ref('')

const isOverview = computed(() => route.name === 'control-panel.index')
const usersActive = computed(() => ['control-panel.users', 'control-panel.edit-user'].includes(route.name))
const rolesActive = computed(() => route.name === 'control-panel.roles')
const tariffsActive = computed(() => ['control-panel.tariffs', 'control-panel.edit-tariff'].includes(route.name))
const paymentsActive = computed(() => route.name === 'control-panel.payments')
const auditActive = computed(() => route.name === 'control-panel.audit')

async function loadOverview() {
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Main.getControlPanel()
		if (response.data?.status !== 'success') {
			throw new Error('Некорректный ответ API панели управления')
		}
		userCount.value = Number(response.data?.user_count || 0)
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
				<p class="cp-subtitle">Пользователи, роли, тарифы, платежи, аудит и системные настройки в едином административном интерфейсе.</p>
			</div>
		</header>

		<nav class="cp-nav" aria-label="Разделы панели управления">
			<router-link :to="{ name: 'control-panel.index' }" class="cp-nav__link">Обзор</router-link>
			<router-link :to="{ name: 'control-panel.users' }" class="cp-nav__link" :class="{ 'router-link-active': usersActive }">Пользователи</router-link>
			<router-link :to="{ name: 'control-panel.roles' }" class="cp-nav__link" :class="{ 'router-link-active': rolesActive }">Роли</router-link>
			<router-link :to="{ name: 'control-panel.tariffs' }" class="cp-nav__link" :class="{ 'router-link-active': tariffsActive }">Тарифы</router-link>
			<router-link :to="{ name: 'control-panel.payments' }" class="cp-nav__link" :class="{ 'router-link-active': paymentsActive }">Платежи</router-link>
			<router-link :to="{ name: 'control-panel.audit' }" class="cp-nav__link" :class="{ 'router-link-active': auditActive }">Аудит</router-link>
		</nav>

		<div v-if="isOverview" class="cp-page">
			<div v-if="isLoading" class="cp-state" role="status">Загружаем административную сводку…</div>
			<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
				<div class="cp-state__stack">
					<strong>{{ loadError }}</strong>
					<BaseButton variant="outline" size="small" text="Повторить" @click="loadOverview" />
				</div>
			</div>

			<div v-else class="cp-overview-grid">
				<article class="cp-card cp-metric-card">
					<span class="cp-metric-card__label">Пользователи</span>
					<strong class="cp-metric-card__value">{{ userCount }}</strong>
					<p class="cp-metric-card__hint">Зарегистрировано в системе</p>
				</article>

				<router-link :to="{ name: 'control-panel.users' }" class="cp-card cp-shortcut-card">
					<div><span class="cp-eyebrow">Аккаунты</span><h2 class="cp-shortcut-card__title">Управление пользователями</h2><p class="cp-card-note">Статус, профиль и безопасность аккаунтов.</p></div>
					<span class="cp-shortcut-card__action">Открыть пользователей →</span>
				</router-link>

				<router-link :to="{ name: 'control-panel.roles' }" class="cp-card cp-shortcut-card">
					<div><span class="cp-eyebrow">Доступ</span><h2 class="cp-shortcut-card__title">Роли и права</h2><p class="cp-card-note">Просмотр назначений и управление системными ролями.</p></div>
					<span class="cp-shortcut-card__action">Открыть роли →</span>
				</router-link>

				<router-link :to="{ name: 'control-panel.tariffs' }" class="cp-card cp-shortcut-card">
					<div><span class="cp-eyebrow">Монетизация</span><h2 class="cp-shortcut-card__title">Тарифные планы</h2><p class="cp-card-note">Стоимость, доступность и продуктовые лимиты.</p></div>
					<span class="cp-shortcut-card__action">Открыть тарифы →</span>
				</router-link>

				<router-link :to="{ name: 'control-panel.payments' }" class="cp-card cp-shortcut-card">
					<div><span class="cp-eyebrow">Платежи</span><h2 class="cp-shortcut-card__title">Платёжные системы</h2><p class="cp-card-note">Test/live режимы, credentials и журнал оплат тарифов.</p></div>
					<span class="cp-shortcut-card__action">Открыть платежи →</span>
				</router-link>

				<router-link :to="{ name: 'control-panel.audit' }" class="cp-card cp-shortcut-card">
					<div><span class="cp-eyebrow">Инциденты</span><h2 class="cp-shortcut-card__title">Аудит действий</h2><p class="cp-card-note">Кто, когда и что изменил — с результатом и request-корреляцией.</p></div>
					<span class="cp-shortcut-card__action">Открыть аудит →</span>
				</router-link>
			</div>
		</div>

		<RouterView />
	</section>
</template>
