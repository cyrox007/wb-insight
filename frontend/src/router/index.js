import { createRouter, createWebHistory } from 'vue-router'


const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes: [
		{
			path: '/',
			name: 'home',
			component: () => import('../pages/HomePage/index.vue'),
			meta: {
				title: "Главная",
				requestGuest: true // Разрешить доступ только неавторизованным пользователям
			}
		},
		{
			path: '/dashboard',
			name: 'dashboard.home',
			component: () => import('../pages/Dashboard/Main/index.vue'),
			meta: {
				title: "Главная",
				requestAuth: true // Разрешить доступ только авторизованным пользователям
			},
			children: []
		},
		{
			path: '/dashboard/profile',
			name: 'dashboard.profile',
			component: () => import('../pages/Dashboard/Profile/index.vue'),
			meta: {
				title: 'Профиль пользователя',
				requestAuth: true
			}
		},
		{
			path: '/dashboard/unity',
			name: 'dashboard.unity',
			component: () => import('../pages/Dashboard/UnityEconomy/index.vue'),
			meta: {
				title: "Unity-экономика",
				requestAuth: true
			}
		},
		{
			path: '/dashboard/ads',
			name: 'dashboard.ads',
			component: () => import('../pages/Dashboard/Ads/AdsPage.vue'),
			meta: {
				title: "Внутренняя реклама",
				requestAuth: true
			}
		},
		{
			path: '/billing/success',
			name: 'billing.success',
			component: () => import('../pages/Billing/Success/index.vue'),
			meta: {
				title: "Успешная оплата",
				requestAuth: true
			}
		},
		{
			path: '/control-panel',
			name: 'control-panel.index',
			component: () => import('../pages/ControlPanel/Main/index.vue'),
			meta: {
				title: "Панель управления",
				requestAuth: true // Разрешить доступ только авторизованным пользователям
				//requestAdmin: true // Разрешить доступ только администраторам
			},
			children: [
				{
					path: 'users',
					name: 'control-panel.users',
					component: () => import('../pages/ControlPanel/Users/index.vue'),
					meta: {
						title: "Пользователи",
						requestAuth: true
					}
				},
				{
					path: 'edit-user/:id',
					name: 'control-panel.edit-user',
					component: () => import('../pages/ControlPanel/Users/edit.vue'),
					meta: {
						title: "Редактировать пользователя",
						requestAuth: true
					}
				},
				{
					path: 'tariffs',
					name: 'control-panel.tariffs',
					component: () => import('../pages/ControlPanel/Tariffs/index.vue'),
					meta: {
						title: "Тарифы",
						requestAuth: true
					}
				},
				{
					path: 'tariffs/:id/edit-tariff',
					name: 'control-panel.edit-tariff',
					component: () => import('../pages/ControlPanel/Tariffs/edit.vue'),
					meta: {
						title: "Редактировать тариф",
						requestAuth: true
					}
				}
			]
		},
		{
			path: '/:pathMatch(.*)*',
			name: 'not-found',
			component: () => import('../pages/NotFoundPage/index.vue'),
			meta: {
				title: "Страница не найдена"
			}
		}
	],
})

const isAuthenticated = () => {
	// Пример проверки токена в localStorage
	const token = localStorage.getItem('access_token')
	const user = localStorage.getItem('user')
	
	if (token && user) {
		try {
			return JSON.stringify(user)
		} catch {
			return null
		}
	}
	return null
}

// Глобальный навигационный хук
router.beforeEach((to, from, next) => {
	// Устанавливаем заголовок страницы
	if (to.meta.title) {
		document.title = to.meta.title
	}
	
	const user = isAuthenticated()
	
	// Проверка маршрутов для авторизованных пользователей
	if (to.meta.requestAuth && !user) {
		// Если маршрут требует авторизации, а пользователь не авторизован
		// Сохраняем URL, на который пытались перейти
		if (to.path !== '/') {
			localStorage.setItem('redirectPath', to.fullPath)
		}
		console.log("НЕАвторизован. Перенаправдяем на панель");
		console.log(`${user}`);
		next({ name: 'home' })
		return
	}
	
	// Проверка маршрутов для гостей (неавторизованных)
	if (to.meta.requestGuest && user) {
		// Если пользователь авторизован, но пытается попасть на страницу для гостей
		// Перенаправляем на дашборд или главную страницу
		console.log("Авторизован. Перенаправдяем на панель");
		
		next({ name: 'dashboard.home' })
		return
	}
	
	// Проверка прав администратора (если нужно)
	if (to.meta.requestAdmin && user) {
		// Здесь добавьте проверку на роль администратора
		// if (!user.is_admin) {
		//     next({ name: 'forbidden' })
		//     return
		// }
	}
	
	// Если все проверки пройдены, разрешаем переход
	next()
})

export default router
