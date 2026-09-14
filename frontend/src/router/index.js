import { createRouter, createWebHistory } from 'vue-router'


const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes: [
		{
			path: '/',
			name: 'home',
			component: () => import('../pages/HomePage/index.vue'),
			meta: {
				title: 'Главная',
				requestGuest: true,
			}
		},
		{
			path: '/dashboard',
			name: 'dashboard.home',
			component: () => import('../pages/Dashboard/Main/index.vue'),
			meta: {
				title: 'Главная',
				requestAuth: true,
			},
			children: [],
		},
		{
			path: '/dashboard/profile',
			name: 'dashboard.profile',
			component: () => import('../pages/Dashboard/Profile/index.vue'),
			meta: {
				title: 'Профиль пользователя',
				requestAuth: true,
			}
		},
		{
			path: '/dashboard/unity',
			name: 'dashboard.unity',
			component: () => import('../pages/Dashboard/UnityEconomy/index.vue'),
			meta: {
				title: 'Unity-экономика',
				requestAuth: true,
			}
		},
		{
			path: '/dashboard/ads',
			name: 'dashboard.ads',
			component: () => import('../pages/Dashboard/Ads/AdsPage.vue'),
			meta: {
				title: 'Внутренняя реклама',
				requestAuth: true,
			}
		},
		{
			path: '/billing/success',
			name: 'billing.success',
			component: () => import('../pages/Billing/Success/index.vue'),
			meta: {
				title: 'Успешная оплата',
				requestAuth: true,
			}
		},
		{
			path: '/control-panel',
			name: 'control-panel.index',
			component: () => import('../pages/ControlPanel/Main/index.vue'),
			meta: {
				title: 'Панель управления',
				requestAuth: true,
				requestAdmin: true,
			},
			children: [
				{
					path: 'users',
					name: 'control-panel.users',
					component: () => import('../pages/ControlPanel/Users/index.vue'),
					meta: {
						title: 'Пользователи',
						requestAuth: true,
					}
				},
				{
					path: 'edit-user/:id',
					name: 'control-panel.edit-user',
					component: () => import('../pages/ControlPanel/Users/edit.vue'),
					meta: {
						title: 'Редактировать пользователя',
						requestAuth: true,
					}
				},
				{
					path: 'tariffs',
					name: 'control-panel.tariffs',
					component: () => import('../pages/ControlPanel/Tariffs/index.vue'),
					meta: {
						title: 'Тарифы',
						requestAuth: true,
					}
				},
				{
					path: 'tariffs/:id/edit-tariff',
					name: 'control-panel.edit-tariff',
					component: () => import('../pages/ControlPanel/Tariffs/edit.vue'),
					meta: {
						title: 'Редактировать тариф',
						requestAuth: true,
					}
				}
			]
		},
		{
			path: '/:pathMatch(.*)*',
			name: 'not-found',
			component: () => import('../pages/NotFoundPage/index.vue'),
			meta: {
				title: 'Страница не найдена',
			}
		}
	],
})

const getAuthenticatedUser = () => {
	const token = localStorage.getItem('access_token')
	const rawUser = localStorage.getItem('user')

	if (!token || !rawUser) {
		return null
	}

	try {
		const user = JSON.parse(rawUser)
		return user && typeof user === 'object' ? user : null
	} catch {
		return null
	}
}

const isAdmin = (user) => {
	return Array.isArray(user?.roles) && user.roles.some(
		(role) => role === 'super_admin' || role === 'admin'
	)
}

router.beforeEach((to, from, next) => {
	if (to.meta.title) {
		document.title = to.meta.title
	}

	const user = getAuthenticatedUser()

	if (to.meta.requestAuth && !user) {
		if (to.path !== '/') {
			localStorage.setItem('redirectPath', to.fullPath)
		}
		next({ name: 'home' })
		return
	}

	if (to.meta.requestGuest && user) {
		next({ name: 'dashboard.home' })
		return
	}

	if (to.meta.requestAdmin && !isAdmin(user)) {
		next({ name: 'dashboard.home' })
		return
	}

	next()
})

export default router
