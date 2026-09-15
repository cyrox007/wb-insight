import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { pinia } from './stores/pinia'
import { useAuthStore } from './stores/auth'

import './styles/variables.css'
import './styles/base.css'

const bootstrap = async () => {
	const app = createApp(App)
	app.use(pinia)

	const authStore = useAuthStore(pinia)
	await authStore.restoreSession()

	app.use(router)
	app.mount('#app')
}

bootstrap()
