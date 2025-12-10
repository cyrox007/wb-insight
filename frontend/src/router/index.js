import { createRouter, createWebHistory } from 'vue-router'

//import HomePage from '../pages/HomePage/index.vue'

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
			path: '/signin',
			name: 'signin',
			component: () => import('../pages/LoginPage/index.vue'),
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
	],
})

export default router
