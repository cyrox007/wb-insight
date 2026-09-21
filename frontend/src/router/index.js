import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { pinia } from '@/stores/pinia'
import { canAccessControlPanel, defaultAuthenticatedRouteName, isStaffUser } from '@/security/roles'


const prefersReducedMotion = () =>
	typeof window !== 'undefined' &&
	typeof window.matchMedia === 'function' &&
	window.matchMedia('(prefers-reduced-motion: reduce)').matches

const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	scrollBehavior(to, from, savedPosition) {
		if (savedPosition) return savedPosition

		const behavior = prefersReducedMotion() ? 'auto' : 'smooth'

		if (to.hash) {
			return {
				el: to.hash,
				top: 84,
				behavior,
			}
		}

		if (to.path !== from.path) {
			return {
				top: 0,
				behavior,
			}
		}

		return false
	},
	routes: [
		{ path: '/', name: 'home', component: () => import('../pages/HomePage/index.vue'), meta: { title: 'Главная', requestGuest: true } },
		{ path: '/legal/:code', name: 'legal.document', component: () => import('../pages/Legal/DocumentPage.vue'), meta: { title: 'Юридический документ · WB Insight' } },
		{ path: '/terms', redirect: '/legal/terms' },
		{ path: '/privacy', redirect: '/legal/privacy' },
		{ path: '/reset-password', name: 'auth.reset-password', component: () => import('../pages/Auth/ResetPassword.vue'), meta: { title: 'Восстановление доступа · WB Insight' } },
		{ path: '/verify-email', name: 'auth.verify-email', component: () => import('../pages/Auth/VerifyEmail.vue'), meta: { title: 'Подтверждение email · WB Insight' } },
		{ path: '/staff', name: 'staff.home', component: () => import('../pages/Staff/Home.vue'), meta: { title: 'Рабочий стол · WB Insight', requestAuth: true, requestStaff: true } },
		{ path: '/dashboard', name: 'dashboard.home', component: () => import('../pages/Dashboard/Main/index.vue'), meta: { title: 'Обзор · WB Insight', requestAuth: true }, children: [] },
		{ path: '/dashboard/profile', name: 'dashboard.profile', component: () => import('../pages/Dashboard/Profile/index.vue'), meta: { title: 'Настройки продавца · WB Insight', requestAuth: true } },
		{ path: '/dashboard/account-security', name: 'dashboard.account-security', component: () => import('../pages/Dashboard/AccountSecurity.vue'), meta: { title: 'Безопасность аккаунта · WB Insight', requestAuth: true } },
		{ path: '/dashboard/unity', name: 'dashboard.unity', component: () => import('../pages/Dashboard/UnityEconomy/index.vue'), meta: { title: 'Юнит-экономика · WB Insight', requestAuth: true } },
		{ path: '/dashboard/finance', name: 'dashboard.finance', component: () => import('../pages/Dashboard/Finance/index.vue'), meta: { title: 'Финансы и выплаты · WB Insight', requestAuth: true } },
		{ path: '/dashboard/stocks', name: 'dashboard.stocks', component: () => import('../pages/Dashboard/Inventory/index.vue'), meta: { title: 'Остатки · WB Insight', requestAuth: true } },
		{ path: '/dashboard/prices', name: 'dashboard.prices', component: () => import('../pages/Dashboard/Prices/index.vue'), meta: { title: 'Цены и скидки · WB Insight', requestAuth: true } },
		{ path: '/dashboard/ads', name: 'dashboard.ads', component: () => import('../pages/Dashboard/Ads/AdsPage.vue'), meta: { title: 'Реклама · WB Insight', requestAuth: true } },
		{ path: '/billing/success', name: 'billing.success', component: () => import('../pages/Billing/Success/index.vue'), meta: { title: 'Успешная оплата', requestAuth: true } },
		{
			path: '/control-panel',
			name: 'control-panel.index',
			component: () => import('../pages/ControlPanel/Main/index.vue'),
			meta: { title: 'Панель управления', requestAuth: true, requestControlPanel: true },
			children: [
				{ path: 'users', name: 'control-panel.users', component: () => import('../pages/ControlPanel/Users/index.vue'), meta: { title: 'Пользователи', requestAuth: true } },
				{ path: 'edit-user/:id', name: 'control-panel.edit-user', component: () => import('../pages/ControlPanel/Users/edit.vue'), meta: { title: 'Редактировать пользователя', requestAuth: true } },
				{ path: 'roles', name: 'control-panel.roles', component: () => import('../pages/ControlPanel/Roles/index.vue'), meta: { title: 'Роли и права', requestAuth: true } },
				{ path: 'tariffs', name: 'control-panel.tariffs', component: () => import('../pages/ControlPanel/Tariffs/index.vue'), meta: { title: 'Тарифы', requestAuth: true } },
				{ path: 'tariffs/:id/edit-tariff', name: 'control-panel.edit-tariff', component: () => import('../pages/ControlPanel/Tariffs/edit.vue'), meta: { title: 'Редактировать тариф', requestAuth: true } },
				{ path: 'payments', name: 'control-panel.payments', component: () => import('../pages/ControlPanel/Payments/index.vue'), meta: { title: 'Платежи', requestAuth: true } },
				{ path: 'mail', name: 'control-panel.mail', component: () => import('../pages/ControlPanel/Mail/index.vue'), meta: { title: 'Рассылки', requestAuth: true } },
				{ path: 'audit', name: 'control-panel.audit', component: () => import('../pages/ControlPanel/Audit/index.vue'), meta: { title: 'Аудит действий', requestAuth: true } }
			]
		},
		{ path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../pages/NotFoundPage/index.vue'), meta: { title: 'Страница не найдена' } }
	],
})


router.beforeEach((to, from, next) => {
	if (to.meta.title) document.title = to.meta.title
	const authStore = useAuthStore(pinia)
	const user = authStore.isAuthenticated ? authStore.user : null
	if (to.meta.requestAuth && !user) {
		if (to.path !== '/') localStorage.setItem('redirectPath', to.fullPath)
		next({ name: 'home' })
		return
	}
	if (to.meta.requestGuest && user) {
		next({ name: defaultAuthenticatedRouteName(user) })
		return
	}
	if (to.meta.requestStaff && !isStaffUser(user)) {
		next({ name: 'dashboard.home' })
		return
	}
	if (to.meta.requestControlPanel && !canAccessControlPanel(user)) {
		next({ name: defaultAuthenticatedRouteName(user) })
		return
	}
	next()
})

export default router
